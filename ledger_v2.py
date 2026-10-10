"""
Integrity layer for the free-space record (formal tier). The detection log is not covered.

Leaves per sample: one ego leaf (t, s, l, psi_rel, kappa; float64) + one 2-byte leaf per sector
  byte 0: free range / 0.5 m (0..255)    byte 1: hit(1) | bearing bin(3) | healthy sensors(2) | 0(2)
Salts: per leaf, salt_i = HMAC-SHA256(block_seed, i)[:16]; only the 32-byte block seed is stored
  (the simulation draws seeds and keys from seeded NumPy generators; a real logger needs a CSPRNG in the HSM)
  (kept with the signing key); disclosing a leaf discloses only its own salt, never the seed.
Block (default 60 s): Merkle root over all leaves, hash of the previous header, signed time range
  [t_first, t_last], hash of the layout (time and sector count of every sample), Ed25519 signature.
  Anchor = hash of the latest header, published periodically (hourly or daily).
Disclosure for a claim: the zone sectors of every sample in the window, the ego leaves, a Merkle
  multiproof and the layout of each disclosed block, and the chain headers from the last block that
  ends before the window up to the anchor (so that no block in the window can be left out).
"""
from __future__ import annotations

import hashlib
import hmac
import struct
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
import numpy as np

SIG_LEN, HASH_LEN, SALT_LEN = 64, 32, 16


def H(*parts: bytes) -> bytes:
    m = hashlib.sha256()
    for p in parts:
        m.update(p)
    return m.digest()


def leaf_hash(salt: bytes, index: int, payload: bytes) -> bytes:
    return H(b"\x00", salt, struct.pack("<I", index), payload)


def node(a: bytes, b: bytes) -> bytes:
    return H(b"\x01", a, b)


def salt_for(seed: bytes, index: int) -> bytes:
    return hmac.new(seed, struct.pack("<I", index), hashlib.sha256).digest()[:SALT_LEN]


def enc_ego(t, log) -> bytes:
    return struct.pack("<5d", float(t), float(log["s"]), float(log["l"]), float(log["psi_rel"]), float(log["kappa"]))


def dec_ego(b: bytes):
    t, s, l, psi, kap = struct.unpack("<5d", b)
    return t, {"s": s, "l": l, "psi_rel": psi, "kappa": kap}


def enc_sector(d, hit, b, n) -> bytes:
    code = int(round(float(d) / 0.5))
    assert 0 <= code <= 255 and 0 <= int(b) <= 7 and 0 <= int(n) <= 3
    return bytes([code, (int(bool(hit)) << 7) | (int(b) << 4) | (int(n) << 2)])


def dec_sector(p: bytes):
    return p[0] * 0.5, bool(p[1] >> 7), (p[1] >> 4) & 7, (p[1] >> 2) & 3


def levels_of(leaves):
    lv = [list(leaves)]
    while len(lv[-1]) > 1:
        cur = lv[-1]
        if len(cur) % 2:
            cur = cur + [cur[-1]]
        lv.append([node(cur[k], cur[k + 1]) for k in range(0, len(cur), 2)])
    return lv


def multiproof(levels, idxs):
    """Sibling hashes needed to recompute the root from the leaves at idxs (sorted, unique)."""
    proof, known = [], set(idxs)
    for lv in levels[:-1]:
        width = len(lv)
        nxt = set()
        for i in sorted(known):
            sib = i ^ 1
            if sib not in known:
                proof.append(lv[sib] if sib < width else lv[i])   # odd level: last node pairs with itself
            nxt.add(i // 2)
        known = nxt
    return proof


def root_from_multiproof(n_leaves, leaf_map, proof):
    """leaf_map: {index: leaf hash}. Recomputes the root consuming proof in the same order."""
    known, it, width = dict(leaf_map), iter(proof), n_leaves
    while width > 1:
        nxt = {}
        for i in sorted(known):
            if i // 2 in nxt:
                continue
            sib = i ^ 1
            if sib in known:
                a, b = (known[i], known[sib]) if i % 2 == 0 else (known[sib], known[i])
            else:
                hs = next(it)
                a, b = (known[i], hs) if i % 2 == 0 else (hs, known[i])
            nxt[i // 2] = node(a, b)
        known, width = nxt, (width + 1) // 2
    leftover = list(it)
    assert not leftover, "unused proof hashes"
    return known[0]


@dataclass
class Header:
    index: int
    prev: bytes
    root: bytes
    n_leaves: int
    layout: list            # [(t, n_sec), ...]
    signature: bytes = b""

    def t_range(self):
        return self.layout[0][0], self.layout[-1][0]

    def body(self) -> bytes:
        lay = b"".join(struct.pack("<dH", t, n) for t, n in self.layout)
        return struct.pack("<II2d", self.index, self.n_leaves, *self.t_range()) + self.prev + self.root + H(lay)

    def layout_bytes(self) -> int:
        return len(self.layout) * 10

    def hash(self) -> bytes:
        return H(b"\x02", self.body(), self.signature)

    def size(self, with_layout=True) -> int:
        """Bytes on the wire: index, leaf count, time range, prev, root, layout hash, signature (184 B);
        a disclosed block also sends its layout, a chain header sends only the layout hash."""
        return 8 + 16 + 3 * HASH_LEN + SIG_LEN + (self.layout_bytes() if with_layout else 0)


@dataclass
class Block:
    header: Header
    payloads: list
    seed: bytes
    levels: list = field(repr=False, default=None)


class LedgerV2:
    def __init__(self, key: Ed25519PrivateKey, rng: np.random.Generator, block_s: float = 60.0):
        self.key, self.rng, self.block_s = key, rng, block_s
        self.blocks: list[Block] = []
        self._pending = []          # (t, log, rec_sample, n_sec)

    def append(self, t, log, smp, n_sec):
        if self._pending and t - self._pending[0][0] >= self.block_s:
            self.seal()
        self._pending.append((t, log, smp, n_sec))

    def seal(self):
        if not self._pending:
            return
        seed = self.rng.bytes(32)
        payloads, layout = [], []
        for t, log, smp, n_sec in self._pending:
            layout.append((float(t), int(n_sec)))
            payloads.append(enc_ego(t, log))
            for i in range(n_sec):
                payloads.append(enc_sector(smp["d_free"][i], smp["hit"][i], smp["bin"][i], smp["ncov"][i]))
        leaves = [leaf_hash(salt_for(seed, k), k, p) for k, p in enumerate(payloads)]
        lv = levels_of(leaves)
        prev = self.blocks[-1].header.hash() if self.blocks else b"\x00" * HASH_LEN
        hd = Header(len(self.blocks), prev, lv[-1][0], len(leaves), layout)
        hd.signature = self.key.sign(hd.body())
        self.blocks.append(Block(hd, payloads, seed, lv))
        self._pending = []

    def anchor(self) -> bytes:
        self.seal()
        return self.blocks[-1].header.hash()

    def storage_bytes(self) -> int:
        """Payload + per-block header + seed (what the vehicle keeps)."""
        return sum(sum(len(p) for p in b.payloads) + b.header.size() + 32 for b in self.blocks)

    # ------------------------------------------------------------------ disclosure
    def disclose(self, t0, t1, sectors_for_sample):
        """sectors_for_sample(t, log, n_sec) -> list of sector indices the claim zone touches."""
        out = {"blocks": [], "headers": []}
        first = None
        for b in self.blocks:
            idx, k = [], 0
            for t, n in b.header.layout:
                if t0 <= t <= t1:
                    _, log = dec_ego(b.payloads[k])
                    idx.append(k)
                    idx += [k + 1 + s for s in sectors_for_sample(t, log, n)]
                k += 1 + n
            if idx:
                first = b.header.index if first is None else first
                idx = sorted(set(idx))
                out["blocks"].append({"index": b.header.index,
                                      "leaves": [(i, b.payloads[i], salt_for(b.seed, i)) for i in idx],
                                      "proof": multiproof(b.levels, idx)})
        if first is not None:
            start = first - 1 if first > 0 else 0          # include the block that ends before the window
            out["headers"] = [b.header for b in self.blocks[start:]]
        return out

    @staticmethod
    def disclosure_bytes(d) -> int:
        disc = {blk["index"] for blk in d["blocks"]}
        n = sum(h.size(with_layout=h.index in disc) for h in d["headers"])
        for blk in d["blocks"]:
            n += sum(4 + len(p) + SALT_LEN for _, p, _ in blk["leaves"]) + HASH_LEN * len(blk["proof"])
        return n


# ---------------------------------------------------------------------- verifier
class VerifyError(Exception):
    pass


def verify(d, pub: Ed25519PublicKey, anchor: bytes, t0, t1, sectors_for_sample):
    """Checks signatures, chain to anchor, Merkle roots, completeness (every sample in the window and
    every zone sector the VERIFIER computes is present). Returns the reconstructed partial record."""
    hdrs = {h.index: h for h in d["headers"]}
    if not d["headers"]:
        raise VerifyError("nothing disclosed")
    for h in d["headers"]:
        try:
            pub.verify(h.signature, h.body())
        except Exception:
            raise VerifyError(f"bad signature on block {h.index}")
    for a, b in zip(d["headers"], d["headers"][1:]):
        if b.prev != a.hash() or b.index != a.index + 1:
            raise VerifyError("broken hash chain")
    if d["headers"][-1].hash() != anchor:
        raise VerifyError("chain does not reach the anchor")
    h0 = d["headers"][0]
    if h0.index != 0 and h0.t_range()[1] >= t0:
        raise VerifyError("chain starts inside the window: an earlier block may have been withheld")
    idxs = [blk["index"] for blk in d["blocks"]]
    if len(set(idxs)) != len(idxs) or idxs != sorted(idxs):
        raise VerifyError("duplicate or reordered blocks")
    if len({h.index for h in d["headers"]}) != len(d["headers"]):
        raise VerifyError("duplicate headers")
    disclosed = set(idxs)
    for h in d["headers"]:                       # signed time ranges only; layouts of chain headers are not sent
        a, b = h.t_range()
        if a <= t1 and b >= t0 and h.index not in disclosed:
            raise VerifyError(f"block {h.index} overlaps the window but was withheld")
    samples, t_prev = [], -float("inf")
    for blk in d["blocks"]:
        if blk["index"] not in hdrs:
            raise VerifyError(f"block {blk['index']} has no header in the chain")
        h = hdrs[blk["index"]]
        li = [i for i, _, _ in blk["leaves"]]
        if len(set(li)) != len(li):
            raise VerifyError(f"duplicate leaves in block {h.index}")
        leaf_map = {i: leaf_hash(salt, i, p) for i, p, salt in blk["leaves"]}
        try:
            root = root_from_multiproof(h.n_leaves, leaf_map, blk["proof"])
        except (StopIteration, AssertionError, KeyError):
            raise VerifyError(f"malformed proof in block {h.index}")
        if root != h.root:
            raise VerifyError(f"Merkle root mismatch in block {h.index}")
        payload = {i: p for i, p, _ in blk["leaves"]}
        k = 0
        for t, n in h.layout:
            if t0 <= t <= t1:
                if k not in payload:
                    raise VerifyError("ego leaf withheld")
                te, log = dec_ego(payload[k])
                if abs(te - t) > 1e-9:
                    raise VerifyError("ego leaf time does not match layout")
                need = sectors_for_sample(t, log, n)
                smp = {"t": t, "log": log, "d_free": np.zeros(n), "hit": np.zeros(n, bool),
                       "bin": np.zeros(n, int), "ncov": np.zeros(n, int)}
                for s in need:
                    if k + 1 + s not in payload:
                        raise VerifyError(f"zone sector {s} withheld at t={t:.2f}")
                    smp["d_free"][s], smp["hit"][s], smp["bin"][s], smp["ncov"][s] = dec_sector(payload[k + 1 + s])
                if t <= t_prev:
                    raise VerifyError("sample times not strictly increasing")
                t_prev = t
                samples.append((n, smp))
            k += 1 + n
    return samples
