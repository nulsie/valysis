from typing import Dict, List, Tuple, Optional
from .product import VSAReducedState
from .intervals import CircularStridedInterval
from .tristate import TristateBitVector


class MemoryRegion:
    __slots__ = ("name", "is_absolute")

    def __init__(self, name: str, is_absolute: bool = False):
        self.name = name
        self.is_absolute = is_absolute

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MemoryRegion):
            return False
        return self.name == other.name

    def __repr__(self) -> str:
        return self.name


AbsoluteRegion = MemoryRegion("Absolute", is_absolute=True)
GlobalRegion = MemoryRegion("Global")


class ValueSet:
    __slots__ = ("bits", "regions", "is_empty")

    def __init__(
        self,
        bits: int,
        regions: Dict[MemoryRegion, VSAReducedState] = None,
        is_empty: bool = False,
    ):
        self.bits = bits
        self.is_empty = is_empty

        if self.is_empty:
            self.regions = {}
            return

        self.regions = {k: v for k, v in (regions or {}).items() if not v.is_empty}
        if not self.regions:
            self.is_empty = True

    @classmethod
    def empty(cls, bits: int = 32) -> "ValueSet":
        return cls(bits, is_empty=True)

    @classmethod
    def absolute(cls, state: VSAReducedState) -> "ValueSet":
        """Creates a pure scalar integer Value-Set."""
        if state.is_empty:
            return cls.empty(state.bits)
        return cls(state.bits, {AbsoluteRegion: state})

    @classmethod
    def pointer(cls, region: MemoryRegion, offset_state: VSAReducedState) -> "ValueSet":
        """Creates a pointer Value-Set to a specific memory region."""
        if offset_state.is_empty:
            return cls.empty(offset_state.bits)
        return cls(offset_state.bits, {region: offset_state})

    def __add__(self, other: "ValueSet") -> "ValueSet":
        assert self.bits == other.bits
        if self.is_empty or other.is_empty:
            return self.empty(self.bits)
    
        new_regions: Dict[MemoryRegion, VSAReducedState] = {}
    
        if AbsoluteRegion in self.regions and AbsoluteRegion in other.regions:
            new_regions[AbsoluteRegion] = (
                self.regions[AbsoluteRegion] + other.regions[AbsoluteRegion]
            )
    
        if AbsoluteRegion in other.regions:
            scalar = other.regions[AbsoluteRegion]
            for reg, offset in self.regions.items():
                if reg.is_absolute:
                    continue
                new_regions[reg] = offset + scalar
    
        if AbsoluteRegion in self.regions:
            scalar = self.regions[AbsoluteRegion]
            for reg, offset in other.regions.items():
                if reg.is_absolute:
                    continue
                if reg in new_regions:
                    new_regions[reg] = new_regions[reg].union(offset + scalar)
                else:
                    new_regions[reg] = offset + scalar
    
        # (v1.1.1)fix: intercept invalid region addition and return top scalar
        if not new_regions:
            top_scalar = VSAReducedState(
                CircularStridedInterval.top(self.bits),
                TristateBitVector.top(self.bits),
            )
            return ValueSet.absolute(top_scalar)
    
        return ValueSet(self.bits, new_regions)

    # (v1.1.1) this was not present before, would've caused crash(soo stupid of me)
    def __sub__(self, other: "ValueSet") -> "ValueSet":
        assert self.bits == other.bits
        if self.is_empty or other.is_empty:
            return self.empty(self.bits)
    
        new_regions: Dict[MemoryRegion, VSAReducedState] = {}
    
        if AbsoluteRegion in self.regions and AbsoluteRegion in other.regions:
            new_regions[AbsoluteRegion] = (
                self.regions[AbsoluteRegion] - other.regions[AbsoluteRegion]
            )
    
        if AbsoluteRegion in other.regions:
            scalar = other.regions[AbsoluteRegion]
            for reg, offset in self.regions.items():
                if reg.is_absolute:
                    continue
                res = offset - scalar
                if reg in new_regions:
                    new_regions[reg] = new_regions[reg].union(res)
                else:
                    new_regions[reg] = res
    
        for reg in self.regions:
            if reg.is_absolute:
                continue
            if reg in other.regions:
                diff = self.regions[reg] - other.regions[reg]
                if AbsoluteRegion in new_regions:
                    new_regions[AbsoluteRegion] = new_regions[AbsoluteRegion].union(diff)
                else:
                    new_regions[AbsoluteRegion] = diff
    
        if not new_regions:
            top_scalar = VSAReducedState(
                CircularStridedInterval.top(self.bits),
                TristateBitVector.top(self.bits),
            )
            return ValueSet.absolute(top_scalar)
    
        return ValueSet(self.bits, new_regions)

    def union(self, other: "ValueSet") -> "ValueSet":
        assert self.bits == other.bits
        if self.is_empty:
            return other
        if other.is_empty:
            return self

        new_regions: Dict[MemoryRegion, VSAReducedState] = {}
        all_regions = set(self.regions.keys()) | set(other.regions.keys())

        for reg in all_regions:
            if reg in self.regions and reg in other.regions:
                new_regions[reg] = self.regions[reg] | other.regions[reg]
            elif reg in self.regions:
                new_regions[reg] = self.regions[reg]
            else:
                new_regions[reg] = other.regions[reg]

        return ValueSet(self.bits, new_regions)

    def intersect(self, other: "ValueSet") -> "ValueSet":
        assert self.bits == other.bits
        if self.is_empty or other.is_empty:
            return self.empty(self.bits)

        new_regions: Dict[MemoryRegion, VSAReducedState] = {}
        common_regions = set(self.regions.keys()) & set(other.regions.keys())

        for reg in common_regions:
            intersected_state = self.regions[reg] & other.regions[reg]
            if not intersected_state.is_empty:
                new_regions[reg] = intersected_state

        return ValueSet(self.bits, new_regions)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ValueSet):
            return False
        if self.is_empty and other.is_empty:
            return True
        if self.is_empty != other.is_empty:
            return False

        if set(self.regions.keys()) != set(other.regions.keys()):
            return False

        for reg in self.regions:

            if self.regions[reg] != other.regions[reg]:
                return False
        return True

    def __repr__(self):
        if self.is_empty:
            return "⊥"
        region_strs = [f"{reg.name} ↦ {offset}" for reg, offset in self.regions.items()]
        return f"VS{{{', '.join(region_strs)}}}"

    def extract(self, high: int, low: int) -> "ValueSet":
        if self.is_empty:
            return self.empty(high - low + 1)
    
        new_regions = {}
        extracted_bits = high - low + 1
    
        for reg, state in self.regions.items():
            extracted_state = state.extract(high, low)
            if not extracted_state.is_empty:
                new_regions[reg] = extracted_state
    
        return ValueSet(extracted_bits, new_regions)

    def concat(self, other: "ValueSet") -> "ValueSet":
        if self.is_empty or other.is_empty:
            return self.empty(self.bits + other.bits)

        all_regs = set(self.regions.keys()) | set(other.regions.keys())

        def get_padded_state(
            vs: "ValueSet", reg: MemoryRegion, bits: int
        ) -> VSAReducedState:
            if reg in vs.regions:
                return vs.regions[reg]
            return VSAReducedState(
                CircularStridedInterval.value(0, bits), TristateBitVector.value(0, bits)
            )

        new_regions = {}

        for reg in all_regs:
            s_state = get_padded_state(self, reg, self.bits)
            o_state = get_padded_state(other, reg, other.bits)

            concatenated_state = s_state.concat(o_state)
            if not concatenated_state.is_empty:
                new_regions[reg] = concatenated_state

        return ValueSet(self.bits + other.bits, new_regions)

    def assume_eq(self, other: "ValueSet") -> tuple["ValueSet", "ValueSet"]:
        if self.is_empty or other.is_empty:
            return self.empty(self.bits), self.empty(self.bits)

        common_regs = set(self.regions.keys()) & set(other.regions.keys())
        s_regions, o_regions = {}, {}

        for reg in common_regs:
            s_ref, o_ref = self.regions[reg].assume_eq(other.regions[reg])
            if not s_ref.is_empty:
                s_regions[reg] = s_ref
            if not o_ref.is_empty:
                o_regions[reg] = o_ref

        return ValueSet(self.bits, s_regions), ValueSet(other.bits, o_regions)

    def assume_ult(self, other: "ValueSet") -> tuple["ValueSet", "ValueSet"]:

        if self.is_empty or other.is_empty:
            return self.empty(self.bits), self.empty(self.bits)

        common_regs = set(self.regions.keys()) & set(other.regions.keys())
        s_regions, o_regions = {}, {}

        for reg in common_regs:
            s_ref, o_ref = self.regions[reg].assume_ult(other.regions[reg])
            if not s_ref.is_empty:
                s_regions[reg] = s_ref
            if not o_ref.is_empty:
                o_regions[reg] = o_ref

        return ValueSet(self.bits, s_regions), ValueSet(other.bits, o_regions)

# (v1.1.1)add: dis has been refactored with a new chunk model for optimization with precision preserved(i tried my best)
class MemoryState:
    __slots__ = ("bits", "addr_mask", "memory", "chunk_taints", "region_taints")

    CHUNK_SHIFT = 8  # 256-byte chunks
    MAX_CHUNKS_PER_TAINT = 1024  # fallback to region taint if bound exceeds 256KB

    def __init__(self, bits: int = 32):
        self.bits = bits
        self.addr_mask = (1 << bits) - 1
        
        # exact offset tracking
        self.memory: Dict["MemoryRegion", Dict[int, "ValueSet"]] = {}
        
        # hierarchical taint overlays
        self.chunk_taints: Dict["MemoryRegion", Dict[int, "ValueSet"]] = {}
        self.region_taints: Dict["MemoryRegion", "ValueSet"] = {}

    def _get_concrete_offsets(
        self, state: VSAReducedState, max_expand: int = 32
    ) -> Optional[List[int]]:
        if state.is_empty:
            return []

        csi = state.interval
        if csi.stride == 0:
            return [csi.lower]

        dist = (csi.upper - csi.lower) & csi.mask
        count = (dist // csi.stride) + 1

        if count > max_expand:
            return None

        offsets = []
        curr = csi.lower
        for _ in range(count):
            offsets.append(curr)
            curr = (curr + csi.stride) & csi.mask

        return offsets

    def _get_taint_ranges(self, csi: CircularStridedInterval, write_size: int) -> List[Tuple[int, int]]:
        """Calculates the absolute bounding boxes for a symbolic write."""
        ranges = []
        if csi.lower <= csi.upper:
            u = csi.upper + write_size - 1
            if u > self.addr_mask:
                ranges.append((csi.lower, self.addr_mask))
                ranges.append((0, u & self.addr_mask))
            else:
                ranges.append((csi.lower, u))
        else:
            # interval wraps around the address space naturally
            ranges.append((csi.lower, self.addr_mask))
            u = csi.upper + write_size - 1
            ranges.append((0, u & self.addr_mask))
        return ranges

    def store(self, address: "ValueSet", value: "ValueSet", size: int, endian: str = "little"):
        byte_slices = None
        is_single_region = (len(address.regions) == 1)
    
        for reg, state in address.regions.items():
            offsets = self._get_concrete_offsets(state)
                
            if offsets is None:
                # OPTIM: hierarchical chunk tainting
                # avoids O(N) loops over existing tracked offsets.
                top_byte = ValueSet.absolute(VSAReducedState(
                    CircularStridedInterval.top(8),
                    TristateBitVector.top(8)
                ))
                
                ranges = self._get_taint_ranges(state.interval, size)
                
                if reg not in self.chunk_taints:
                    self.chunk_taints[reg] = {}
                    
                for start, end in ranges:
                    start_chunk = start >> self.CHUNK_SHIFT
                    end_chunk = end >> self.CHUNK_SHIFT
                    
                    if (end_chunk - start_chunk) > self.MAX_CHUNKS_PER_TAINT:
                        # fallback to O(1) region-wide taint if completely unbounded
                        existing_region_taint = self.region_taints.get(reg)
                        if existing_region_taint:
                            self.region_taints[reg] = existing_region_taint.union(top_byte)
                        else:
                            self.region_taints[reg] = top_byte
                    else:
                        # apply O(1) chunk taints
                        for c in range(start_chunk, end_chunk + 1):
                            existing_chunk = self.chunk_taints[reg].get(c)
                            if existing_chunk:
                                self.chunk_taints[reg][c] = existing_chunk.union(top_byte)
                            else:
                                self.chunk_taints[reg][c] = top_byte
                continue
    
            is_strong_update = is_single_region and (len(offsets) == 1)
    
            for off in offsets:
                if reg not in self.memory:
                    self.memory[reg] = {}
                        
                if is_strong_update:
                    for i in range(size):
                        target_byte_off = (off + i) & self.addr_mask
                        self.memory[reg][target_byte_off] = (value, size, i, endian)
                else:
                    if byte_slices is None:
                        byte_slices = []
                        for i in range(size):
                            low = i * 8 if endian == "little" else (size - 1 - i) * 8
                            byte_slices.append(value.extract(low + 7, low))
    
                    for i in range(size):
                        target_byte_off = (off + i) & self.addr_mask
                        slice_val = byte_slices[i]
    
                        existing = self.memory[reg].get(target_byte_off)
                        if existing is not None:
                            if isinstance(existing, tuple):
                                e_val, e_size, e_idx, e_endian = existing
                                e_low = e_idx * 8 if e_endian == "little" else (e_size - 1 - e_idx) * 8
                                existing_val = e_val.extract(e_low + 7, e_low)
                            else:
                                existing_val = existing
                            self.memory[reg][target_byte_off] = existing_val.union(slice_val)
                        else:
                            self.memory[reg][target_byte_off] = slice_val

    def load(self, address: "ValueSet", size: int, endian: str = "little") -> "ValueSet":
        if address.is_empty:
            return ValueSet.empty(size * 8)

        result_val = ValueSet.empty(size * 8)

        for reg, state in address.regions.items():
            offsets = self._get_concrete_offsets(state)

            if offsets is None:
                top_val = ValueSet.absolute(
                    VSAReducedState(
                        CircularStridedInterval.top(size * 8),
                        TristateBitVector.top(size * 8),
                    )
                )
                result_val = result_val.union(top_val)
                continue

            for off in offsets:
                slices = []
                i = 0

                while i < size:
                    target_byte_off = (off + i) & self.addr_mask
                    entry = self.memory.get(reg, {}).get(target_byte_off)

                    # extract chunk and region taints dynamically
                    c_idx = target_byte_off >> self.CHUNK_SHIFT
                    chunk_taint = self.chunk_taints.get(reg, {}).get(c_idx)
                    region_taint = self.region_taints.get(reg)

                    if isinstance(entry, tuple):
                        e_val, e_size, e_idx, e_endian = entry

                        if e_endian == endian:
                            run_len = 1
                            while (i + run_len) < size:
                                nxt_off = (off + i + run_len) & self.addr_mask
                                nxt_entry = self.memory.get(reg, {}).get(nxt_off)
                                if (
                                    isinstance(nxt_entry, tuple)
                                    and nxt_entry[0] is e_val
                                    and nxt_entry[1] == e_size
                                    and nxt_entry[3] == e_endian
                                    and nxt_entry[2] == e_idx + run_len
                                ):
                                    run_len += 1
                                else:
                                    break

                            if e_endian == "little":
                                low_bit = e_idx * 8
                                high_bit = (e_idx + run_len) * 8 - 1
                            else:
                                low_bit = (e_size - e_idx - run_len) * 8
                                high_bit = (e_size - 1 - e_idx) * 8 + 7

                            extracted_slice = e_val.extract(high_bit, low_bit)
                            
                            # apply taints to the multi-byte vector slice if any sub-byte overlaps a taint
                            has_taint = region_taint is not None
                            if not has_taint:
                                for j in range(run_len):
                                    sub_c_idx = ((off + i + j) & self.addr_mask) >> self.CHUNK_SHIFT
                                    if sub_c_idx in self.chunk_taints.get(reg, {}):
                                        has_taint = True
                                        break
                                        
                            if has_taint:
                                top_slice = ValueSet.absolute(VSAReducedState(
                                    CircularStridedInterval.top(run_len * 8),
                                    TristateBitVector.top(run_len * 8)
                                ))
                                extracted_slice = extracted_slice.union(top_slice)

                            slices.append(extracted_slice)
                            i += run_len
                            continue

                        e_low = e_idx * 8 if e_endian == "little" else (e_size - 1 - e_idx) * 8
                        resolved_byte = e_val.extract(e_low + 7, e_low)
                    elif entry is not None:
                        resolved_byte = entry
                    else:
                        resolved_byte = ValueSet.absolute(VSAReducedState(
                            CircularStridedInterval.top(8),
                            TristateBitVector.top(8)
                        ))

                    # apply chunk and region taints to single-byte resolution
                    if region_taint:
                        resolved_byte = resolved_byte.union(region_taint)
                    if chunk_taint:
                        resolved_byte = resolved_byte.union(chunk_taint)

                    slices.append(resolved_byte)
                    i += 1

                if endian == "little":
                    reconstructed = slices[0]
                    for s in slices[1:]:
                        reconstructed = s.concat(reconstructed)
                else:
                    reconstructed = slices[0]
                    for s in slices[1:]:
                        reconstructed = reconstructed.concat(s)

                result_val = result_val.union(reconstructed)

        return result_val

    def __repr__(self):
        out = []
        for reg, cells in self.memory.items():
            if cells or reg in self.chunk_taints or reg in self.region_taints:
                out.append(f"--- {reg.name} ---")
                
                # print explicit exact tracking
                if cells:
                    sorted_offs = sorted(cells.keys())
                    for off in sorted_offs:
                        val = cells[off]
                        if isinstance(val, tuple):
                            e_val, _, e_idx, _ = val
                            out.append(f"  [0x{off:x} : 1 byte] = LazySlice(idx={e_idx}) of {e_val}")
                        else:
                            out.append(f"  [0x{off:x} : 1 byte] = {val}")
                            
                # print overlayed taints
                if reg in self.region_taints:
                    out.append(f"  [REGION WIDE TAINT] = {self.region_taints[reg]}")
                elif reg in self.chunk_taints and self.chunk_taints[reg]:
                    sorted_chunks = sorted(self.chunk_taints[reg].keys())
                    for c in sorted_chunks:
                        c_start = c << self.CHUNK_SHIFT
                        c_end = c_start + (1 << self.CHUNK_SHIFT) - 1
                        out.append(f"  [CHUNK 0x{c_start:x}-0x{c_end:x} TAINT] = {self.chunk_taints[reg][c]}")
                        
        return "\n".join(out) if out else "MemoryState { Empty }"
