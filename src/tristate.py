class TristateBitVector:
    __slots__ = ('bits', 'mask', 'ones', 'zeros', 'is_empty')

    def __init__(self, bits: int, ones: int, zeros: int, is_empty: bool = False):
        self.bits = bits
        self.mask = (1 << bits) - 1
        self.is_empty = is_empty
        
        if self.is_empty:
            self.ones, self.zeros = 0, 0
            return
            
        self.ones = ones & self.mask
        self.zeros = zeros & self.mask
        
                                                                                    
        if (self.ones & self.zeros) != 0:
            self.is_empty = True
            self.ones, self.zeros = 0, 0

    @classmethod
    def top(cls, bits: int = 32) -> 'TristateBitVector':
        return cls(bits, ones=0, zeros=0)

    @classmethod
    def empty(cls, bits: int = 32) -> 'TristateBitVector':
        return cls(bits, ones=0, zeros=0, is_empty=True)

    @classmethod
    def value(cls, val: int, bits: int = 32) -> 'TristateBitVector':
        val = val & ((1 << bits) - 1)
        return cls(bits, ones=val, zeros=~val)

    @property
    def unknown(self) -> int:
        if self.is_empty: return 0
        return ~(self.ones | self.zeros) & self.mask

    def __and__(self, other: 'TristateBitVector') -> 'TristateBitVector':
        if self.is_empty or other.is_empty: return self.empty(self.bits)
                                          
        n_ones = self.ones & other.ones
        n_zeros = self.zeros | other.zeros
        return TristateBitVector(self.bits, n_ones, n_zeros)

    def __or__(self, other: 'TristateBitVector') -> 'TristateBitVector':
        if self.is_empty or other.is_empty: return self.empty(self.bits)
                                        
        n_ones = self.ones | other.ones
        n_zeros = self.zeros & other.zeros
        return TristateBitVector(self.bits, n_ones, n_zeros)

    def __xor__(self, other: 'TristateBitVector') -> 'TristateBitVector':
        if self.is_empty or other.is_empty: return self.empty(self.bits)
                                  
        n_ones = (self.ones & other.zeros) | (self.zeros & other.ones)
                                  
        n_zeros = (self.ones & other.ones) | (self.zeros & other.zeros)
        return TristateBitVector(self.bits, n_ones, n_zeros)

    def __invert__(self) -> 'TristateBitVector':
        if self.is_empty: return self
                                        
        return TristateBitVector(self.bits, ones=self.zeros, zeros=self.ones)
        
    def get_min_max(self) -> tuple[int, int]:
        if self.is_empty: raise ValueError("Empty state has no min/max")
        min_val = self.ones
        max_val = self.ones | self.unknown
        return min_val, max_val
                                                                                                                                                                                            
    def zero_extend(self, new_bits: int) -> 'TristateBitVector':
        if self.is_empty: return self.empty(new_bits)
        if new_bits <= self.bits: return self
            
        new_mask = (1 << new_bits) - 1
        high_zeros = new_mask ^ self.mask                                                   
            
        return self.__class__(new_bits, self.ones, self.zeros | high_zeros)
    
    def sign_extend(self, new_bits: int) -> 'TristateBitVector':
        if self.is_empty: return self.empty(new_bits)
        if new_bits <= self.bits: return self
            
        sign_bit_mask = 1 << (self.bits - 1)
        new_mask = (1 << new_bits) - 1
        high_bits = new_mask ^ self.mask
            
        if self.ones & sign_bit_mask:
                                                 
            return self.__class__(new_bits, self.ones | high_bits, self.zeros)
        elif self.zeros & sign_bit_mask:
                                                 
            return self.__class__(new_bits, self.ones, self.zeros | high_bits)
        else:
                                                                                   
            return self.__class__(new_bits, self.ones, self.zeros)
    
    def truncate(self, new_bits: int) -> 'TristateBitVector':
        if self.is_empty: return self.empty(new_bits)
        if new_bits >= self.bits: return self
            
        new_mask = (1 << new_bits) - 1
        return self.__class__(new_bits, self.ones & new_mask, self.zeros & new_mask)
    
    def extract(self, high: int, low: int) -> 'TristateBitVector':
        if self.is_empty: return self.empty(high - low + 1)
        new_bits = high - low + 1
        new_mask = (1 << new_bits) - 1
            
        n_ones = (self.ones >> low) & new_mask
        n_zeros = (self.zeros >> low) & new_mask
        return self.__class__(new_bits, n_ones, n_zeros)
    
    def concat(self, other: 'TristateBitVector') -> 'TristateBitVector':
        if self.is_empty or other.is_empty:
            return self.empty(self.bits + other.bits)
                
        new_bits = self.bits + other.bits
        n_ones = (self.ones << other.bits) | other.ones
        n_zeros = (self.zeros << other.bits) | other.zeros
            
        return self.__class__(new_bits, n_ones, n_zeros)
                                                                                                                                                                                                         
    def intersect(self, other: 'TristateBitVector') -> 'TristateBitVector':
        if self.is_empty or other.is_empty: return self.empty(self.bits)
        assert self.bits == other.bits
        
        return TristateBitVector(
            self.bits,
            ones=self.ones | other.ones,                                                             
            zeros=self.zeros | other.zeros                                                           
        )
    
    def assume_eq(self, other: 'TristateBitVector') -> tuple['TristateBitVector', 'TristateBitVector']:
        intersected = self & other
        return intersected, intersected
    
    def assume_neq(self, other: 'TristateBitVector') -> tuple['TristateBitVector', 'TristateBitVector']:
        return self, other
    
    def assume_ult(self, other: 'TristateBitVector') -> tuple['TristateBitVector', 'TristateBitVector']:
        if self.is_empty or other.is_empty:
            return self.empty(self.bits), other.empty(other.bits)
                
        _, b_max = other.get_min_max()
            
        if b_max == 0:
                                                                                                                  
            return self.empty(self.bits), self.empty(other.bits)
                                                                                    
        a_max_possible = b_max - 1
                                                                                                                                                               
        leading_zeros_mask = self.mask & ~((1 << a_max_possible.bit_length()) - 1)
            
        if leading_zeros_mask != 0:
                                                           
            n_zeros = self.zeros | leading_zeros_mask
            refined_self = self.__class__(self.bits, self.ones, n_zeros)
            return refined_self, other
                
        return self, other
                                             
    def join(self, other: 'TristateBitVector') -> 'TristateBitVector':
        if self.is_empty: return other
        if other.is_empty: return self
        assert self.bits == other.bits
        
        return TristateBitVector(
            self.bits,
            ones=self.ones & other.ones,                                     
            zeros=self.zeros & other.zeros                                    
        )
