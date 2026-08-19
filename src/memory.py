from typing import Dict, List, Tuple, Optional
from .product import VSAReducedState
from .intervals import CircularStridedInterval
from .tristate import TristateBitVector

class MemoryRegion:
    __slots__ = ('name', 'is_absolute')

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
    __slots__ = ('bits', 'regions', 'is_empty')

    def __init__(self, bits: int, regions: Dict[MemoryRegion, VSAReducedState] = None, is_empty: bool = False):
        self.bits = bits
        self.is_empty = is_empty
        
        if self.is_empty:
            self.regions = {}
            return
            
        self.regions = {k: v for k, v in (regions or {}).items() if not v.is_empty}
        if not self.regions:
            self.is_empty = True

    @classmethod
    def empty(cls, bits: int = 32) -> 'ValueSet':
        return cls(bits, is_empty=True)

    @classmethod
    def absolute(cls, state: VSAReducedState) -> 'ValueSet':
        """Creates a pure scalar integer Value-Set."""
        if state.is_empty:
            return cls.empty(state.bits)
        return cls(state.bits, {AbsoluteRegion: state})

    @classmethod
    def pointer(cls, region: MemoryRegion, offset_state: VSAReducedState) -> 'ValueSet':
        """Creates a pointer Value-Set to a specific memory region."""
        if offset_state.is_empty:
            return cls.empty(offset_state.bits)
        return cls(offset_state.bits, {region: offset_state})
                                                                                                                                                                                          
    def __add__(self, other: 'ValueSet') -> 'ValueSet':
        assert self.bits == other.bits
        if self.is_empty or other.is_empty:
            return self.empty(self.bits)

        new_regions: Dict[MemoryRegion, VSAReducedState] = {}
                                                                     
        if AbsoluteRegion in self.regions and AbsoluteRegion in other.regions:
            new_regions[AbsoluteRegion] = self.regions[AbsoluteRegion] + other.regions[AbsoluteRegion]
                                                 
        if AbsoluteRegion in other.regions:
            scalar = other.regions[AbsoluteRegion]
            for reg, offset in self.regions.items():
                if reg.is_absolute: continue
                new_regions[reg] = offset + scalar
                                                   
        if AbsoluteRegion in self.regions:
            scalar = self.regions[AbsoluteRegion]
            for reg, offset in other.regions.items():
                if reg.is_absolute: continue
                new_regions[reg] = offset + scalar

        return ValueSet(self.bits, new_regions)
                                                                                                                                                                            
    def union(self, other: 'ValueSet') -> 'ValueSet':
        assert self.bits == other.bits
        if self.is_empty: return other
        if other.is_empty: return self

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

    def intersect(self, other: 'ValueSet') -> 'ValueSet':
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
        if not isinstance(other, ValueSet): return False
        if self.is_empty and other.is_empty: return True
        if self.is_empty != other.is_empty: return False
        
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
                                                                                                                                                                                             
    def extract(self, high: int, low: int) -> 'ValueSet':
        if self.is_empty: 
            return self.empty(high - low + 1)
                
        new_regions = {}
        for reg, state in self.regions.items():
            extracted_state = state.extract(high, low)
            if not extracted_state.is_empty:
                new_regions[reg] = extracted_state
                    
        return ValueSet(high - low + 1, new_regions)
    
    def concat(self, other: 'ValueSet') -> 'ValueSet':
        if self.is_empty or other.is_empty:
            return self.empty(self.bits + other.bits)
                
        new_regions = {}
        all_regs = set(self.regions.keys()) | set(other.regions.keys())
            
        def get_padded_state(vs: 'ValueSet', reg: MemoryRegion, bits: int) -> VSAReducedState:
            if reg in vs.regions:
                return vs.regions[reg]
            return VSAReducedState(
                CircularStridedInterval.value(0, bits), 
                TristateBitVector.value(0, bits)
            )
            
        for reg in all_regs:
            s_state = get_padded_state(self, reg, self.bits)
            o_state = get_padded_state(other, reg, other.bits)
                
            concatenated_state = s_state.concat(o_state)
            if not concatenated_state.is_empty:
                new_regions[reg] = concatenated_state
                    
        return ValueSet(self.bits + other.bits, new_regions)

class MemoryState:
    __slots__ = ('bits', 'addr_mask', 'memory')

    def __init__(self, bits: int = 32):
        self.bits = bits
        self.addr_mask = (1 << bits) - 1
                                                                                  
        self.memory: Dict[MemoryRegion, Dict[int, ValueSet]] = {}

    def _get_concrete_offsets(self, state: VSAReducedState, max_expand: int = 32) -> Optional[List[int]]:
        if state.is_empty: return []
            
        csi = state.interval
        if csi.stride == 0: return [csi.lower]
            
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
                                                                                                                                                                              
    def store(self, address: ValueSet, value: ValueSet, size: int, endian: str = 'little') -> None:
        if address.is_empty or value.is_empty: return
                                                             
        is_strong_update = False
        if len(address.regions) == 1:
            for reg, state in address.regions.items():
                offsets = self._get_concrete_offsets(state)
                if offsets is not None and len(offsets) == 1:
                    is_strong_update = True
                                              
        byte_slices = []
        for i in range(size):
            if endian == 'little':
                low = i * 8
            else:
                low = (size - 1 - i) * 8
            byte_slices.append(value.extract(low + 7, low))
    
        for reg, state in address.regions.items():
            if reg not in self.memory:
                self.memory[reg] = {}
    
            offsets = self._get_concrete_offsets(state)
                
            if offsets is None:
                                                              
                self.memory[reg].clear()
                continue
                    
            for off in offsets:
                for i in range(size):
                    target_byte_off = (off + i) & self.addr_mask
                    slice_val = byte_slices[i]
                        
                    if is_strong_update:
                        self.memory[reg][target_byte_off] = slice_val
                    else:
                        if target_byte_off in self.memory[reg]:
                            existing_val = self.memory[reg][target_byte_off]
                            self.memory[reg][target_byte_off] = existing_val.union(slice_val)
                        else:
                                                                                               
                            top_byte = ValueSet.absolute(VSAReducedState(
                                CircularStridedInterval.top(8),
                                TristateBitVector.top(8)
                            ))
                            self.memory[reg][target_byte_off] = top_byte.union(slice_val)
    
    def load(self, address: ValueSet, size: int, endian: str = 'little') -> ValueSet:
        if address.is_empty: return ValueSet.empty(size * 8)
    
        result_val = ValueSet.empty(size * 8)
            
        for reg, state in address.regions.items():
            offsets = self._get_concrete_offsets(state)
                
            if offsets is None:
                                                    
                top_val = ValueSet.absolute(VSAReducedState(
                    CircularStridedInterval.top(size * 8),
                    TristateBitVector.top(size * 8)
                ))
                result_val = result_val.union(top_val)
                continue
                    
            for off in offsets:
                loaded_bytes = []
                for i in range(size):
                    target_byte_off = (off + i) & self.addr_mask
                    if target_byte_off in self.memory.get(reg, {}):
                        loaded_bytes.append(self.memory[reg][target_byte_off])
                    else:
                                                                     
                        top_byte = ValueSet.absolute(VSAReducedState(
                            CircularStridedInterval.top(8),
                            TristateBitVector.top(8)
                        ))
                        loaded_bytes.append(top_byte)
                                                                               
                if endian == 'little':
                    reconstructed = loaded_bytes[0]
                    for i in range(1, size):
                        reconstructed = loaded_bytes[i].concat(reconstructed)
                else:
                    reconstructed = loaded_bytes[0]
                    for i in range(1, size):
                        reconstructed = reconstructed.concat(loaded_bytes[i])
                            
                result_val = result_val.union(reconstructed)
    
        return result_val
    
    def __repr__(self):
        out = []
        for reg, cells in self.memory.items():
            if cells:
                out.append(f"--- {reg.name} ---")
                                                                
                sorted_offs = sorted(cells.keys())
                for off in sorted_offs:
                    val = cells[off]
                    out.append(f"  [0x{off:x} : 1 byte] = {val}")
        return "\n".join(out) if out else "MemoryState { Empty }"
                                                                                                                                                                                                            
    def assume_eq(self, other: 'ValueSet') -> tuple['ValueSet', 'ValueSet']:
        if self.is_empty or other.is_empty:
            return self.empty(self.bits), self.empty(self.bits)
    
        common_regs = set(self.regions.keys()) & set(other.regions.keys())
        s_regions, o_regions = {}, {}
    
        for reg in common_regs:
            s_ref, o_ref = self.regions[reg].assume_eq(other.regions[reg])
            if not s_ref.is_empty: s_regions[reg] = s_ref
            if not o_ref.is_empty: o_regions[reg] = o_ref
    
        return ValueSet(self.bits, s_regions), ValueSet(other.bits, o_regions)
    
    def assume_ult(self, other: 'ValueSet') -> tuple['ValueSet', 'ValueSet']:
                                                                                              
        if self.is_empty or other.is_empty:
            return self.empty(self.bits), self.empty(self.bits)
    
        common_regs = set(self.regions.keys()) & set(other.regions.keys())
        s_regions, o_regions = {}, {}
    
        for reg in common_regs:
            s_ref, o_ref = self.regions[reg].assume_ult(other.regions[reg])
            if not s_ref.is_empty: s_regions[reg] = s_ref
            if not o_ref.is_empty: o_regions[reg] = o_ref
    
        return ValueSet(self.bits, s_regions), ValueSet(other.bits, o_regions)
