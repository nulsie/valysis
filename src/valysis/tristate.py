import functools


class TristateBitVector:
    __slots__ = ("bits", "mask", "ones", "zeros", "is_empty")

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
    @functools.lru_cache(maxsize=32)
    def top(cls, bits: int = 32) -> "TristateBitVector":
        return cls(bits, ones=0, zeros=0)

    @classmethod
    @functools.lru_cache(maxsize=32)
    def empty(cls, bits: int = 32) -> "TristateBitVector":
        return cls(bits, ones=0, zeros=0, is_empty=True)

    @classmethod
    def value(cls, val: int, bits: int = 32) -> "TristateBitVector":
        val = val & ((1 << bits) - 1)
        return cls(bits, ones=val, zeros=~val)

    @property
    def unknown(self) -> int:
        if self.is_empty:
            return 0
        return ~(self.ones | self.zeros) & self.mask

    # v1.1.1 fix(bitwise destruction on arithmetic) i'm gonna add a bitwise 'addition' addition here which seems sound and precise, and call it from product.py
    def __add__(self, other: "TristateBitVector") -> "TristateBitVector":
        if self.is_empty or other.is_empty:
            return self.empty(self.bits)
    
        # O(1) swar addition
        # 1. compute the absolute minimum sum (assuming all unknown bits are 0)
        min_sum = (self.ones + other.ones) & self.mask
            
        # 2. compute the absolute maximum sum (assuming all unknown bits are 1)
        max_a = self.ones | self.unknown
        max_b = other.ones | other.unknown
        max_sum = (max_a + max_b) & self.mask
            
        # 3. a bit is mathematically unknown if it differs between the min and max 
        # sums (meaning a carry flipped it), OR if it was already unknown in the operands.
        res_unknown = (min_sum ^ max_sum) | self.unknown | other.unknown
            
        # 4. extract the definitive 1s and 0s
        res_ones = min_sum & ~res_unknown
        res_zeros = ~(res_ones | res_unknown) & self.mask
            
        return self.__class__(self.bits, res_ones, res_zeros)

    def __and__(self, other: "TristateBitVector") -> "TristateBitVector":
        if self.is_empty or other.is_empty:
            return self.empty(self.bits)

        n_ones = self.ones & other.ones
        n_zeros = self.zeros | other.zeros
        return TristateBitVector(self.bits, n_ones, n_zeros)

    def __or__(self, other: "TristateBitVector") -> "TristateBitVector":
        if self.is_empty or other.is_empty:
            return self.empty(self.bits)

        n_ones = self.ones | other.ones
        n_zeros = self.zeros & other.zeros
        return TristateBitVector(self.bits, n_ones, n_zeros)

    def __xor__(self, other: "TristateBitVector") -> "TristateBitVector":
        if self.is_empty or other.is_empty:
            return self.empty(self.bits)

        n_ones = (self.ones & other.zeros) | (self.zeros & other.ones)

        n_zeros = (self.ones & other.ones) | (self.zeros & other.zeros)
        return TristateBitVector(self.bits, n_ones, n_zeros)

    def __invert__(self) -> "TristateBitVector":
        if self.is_empty:
            return self

        return TristateBitVector(self.bits, ones=self.zeros, zeros=self.ones)

    def get_min_max(self) -> tuple[int, int]:
        if self.is_empty:
            raise ValueError("Empty state has no min/max")
        min_val = self.ones
        max_val = self.ones | self.unknown
        return min_val, max_val

    def zero_extend(self, new_bits: int) -> "TristateBitVector":
        if self.is_empty:
            return self.empty(new_bits)
        if new_bits <= self.bits:
            return self

        new_mask = (1 << new_bits) - 1
        high_zeros = new_mask ^ self.mask

        return self.__class__(new_bits, self.ones, self.zeros | high_zeros)

    def sign_extend(self, new_bits: int) -> "TristateBitVector":
        if self.is_empty:
            return self.empty(new_bits)
        if new_bits <= self.bits:
            return self

        sign_bit_mask = 1 << (self.bits - 1)
        new_mask = (1 << new_bits) - 1
        high_bits = new_mask ^ self.mask

        if self.ones & sign_bit_mask:

            return self.__class__(new_bits, self.ones | high_bits, self.zeros)
        elif self.zeros & sign_bit_mask:

            return self.__class__(new_bits, self.ones, self.zeros | high_bits)
        else:

            return self.__class__(new_bits, self.ones, self.zeros)

    def truncate(self, new_bits: int) -> "TristateBitVector":
        if self.is_empty:
            return self.empty(new_bits)
        if new_bits >= self.bits:
            return self

        new_mask = (1 << new_bits) - 1
        return self.__class__(new_bits, self.ones & new_mask, self.zeros & new_mask)

    def extract(self, high: int, low: int) -> "TristateBitVector":
        if self.is_empty:
            return self.empty(high - low + 1)
        new_bits = high - low + 1
        new_mask = (1 << new_bits) - 1

        n_ones = (self.ones >> low) & new_mask
        n_zeros = (self.zeros >> low) & new_mask
        return self.__class__(new_bits, n_ones, n_zeros)

    def concat(self, other: "TristateBitVector") -> "TristateBitVector":
        if self.is_empty or other.is_empty:
            return self.empty(self.bits + other.bits)

        new_bits = self.bits + other.bits
        n_ones = (self.ones << other.bits) | other.ones
        n_zeros = (self.zeros << other.bits) | other.zeros

        return self.__class__(new_bits, n_ones, n_zeros)

    def intersect(self, other: "TristateBitVector") -> "TristateBitVector":
        if self.is_empty or other.is_empty:
            return self.empty(self.bits)
        assert self.bits == other.bits

        return TristateBitVector(
            self.bits, ones=self.ones | other.ones, zeros=self.zeros | other.zeros
        )

    def assume_eq(
        self, other: "TristateBitVector"
    ) -> tuple["TristateBitVector", "TristateBitVector"]:
        intersected = self & other
        return intersected, intersected

    def assume_neq(
        self, other: "TristateBitVector"
    ) -> tuple["TristateBitVector", "TristateBitVector"]:
        return self, other

    def assume_ult(
        self, other: "TristateBitVector"
    ) -> tuple["TristateBitVector", "TristateBitVector"]:
        if self.is_empty or other.is_empty:
            return self.empty(self.bits), other.empty(other.bits)

        _, b_max = other.get_min_max()

        if b_max == 0:

            return self.empty(self.bits), other

        a_max_possible = b_max - 1

        leading_zeros_mask = self.mask & ~((1 << a_max_possible.bit_length()) - 1)

        if leading_zeros_mask != 0:

            n_zeros = self.zeros | leading_zeros_mask
            refined_self = self.__class__(self.bits, self.ones, n_zeros)
            return refined_self, other

        return self, other

    def join(self, other: "TristateBitVector") -> "TristateBitVector":
        if self.is_empty:
            return other
        if other.is_empty:
            return self
        assert self.bits == other.bits

        return TristateBitVector(
            self.bits, ones=self.ones & other.ones, zeros=self.zeros & other.zeros
        )

    # (v1.1.1) add: bitwise shifts (__lshift__, __rshift__, and arithmetic shifts) and mul for tbv and vsars
    # dis kinda like _extract_shift_amount in intervals.py but a bit diff so i named it _get :3
    def _get_shift_amounts(self, shift_val) -> list[int]:
        if isinstance(shift_val, int):
            return [shift_val]
    
        if hasattr(shift_val, "ones") and hasattr(shift_val, "zeros"):
            if shift_val.is_empty:
                return []
            valid_shifts = []
            max_val = shift_val.ones | shift_val.unknown
            if max_val >= self.bits:
                valid_shifts.append(self.bits)
            for i in range(self.bits):
                if (i & shift_val.zeros) == 0 and ((~i & self.mask) & shift_val.ones) == 0:
                    valid_shifts.append(i)
            return valid_shifts
    
        if hasattr(shift_val, "lower") and hasattr(shift_val, "upper"):
            if shift_val.is_empty:
                return []
            valid = []
            for p in shift_val.split_if_wrapped():
                curr = p.lower
                count = 0
                max_elems = ((p.upper - p.lower) // p.stride + 1) if p.stride > 0 else 1
                while count < min(max_elems, self.bits):
                    v = curr % self.bits
                    if v not in valid:
                        valid.append(v)
                    if curr == p.upper:
                        break
                    curr = (curr + p.stride) & p.mask
                    count += 1
            return valid
    
        return []
    
    def __lshift__(self, shift_val) -> "TristateBitVector":
        if self.is_empty:
            return self
                
        amounts = self._get_shift_amounts(shift_val)
        if not amounts:
            return self.empty(self.bits)
                
        result_ones, result_zeros = self.mask, self.mask
        is_first = True
            
        for s in amounts:
            if s >= self.bits:
                s_ones = 0
                s_zeros = self.mask
            else:
                s_ones = (self.ones << s) & self.mask
                s_zeros = ((self.zeros << s) | ((1 << s) - 1)) & self.mask
                
            if is_first:
                result_ones, result_zeros = s_ones, s_zeros
                is_first = False
            else:
                result_ones &= s_ones
                result_zeros &= s_zeros
                    
        return self.__class__(self.bits, result_ones, result_zeros)
    
    def __rshift__(self, shift_val) -> "TristateBitVector":
        if self.is_empty:
            return self
                
        amounts = self._get_shift_amounts(shift_val)
        if not amounts:
            return self.empty(self.bits)
                
        result_ones, result_zeros = self.mask, self.mask
        is_first = True
            
        for s in amounts:
            if s >= self.bits:
                s_ones = 0
                s_zeros = self.mask
            else:
                s_ones = self.ones >> s
                high_zeros = self.mask & ~(self.mask >> s)
                s_zeros = (self.zeros >> s) | high_zeros
                    
            if is_first:
                result_ones, result_zeros = s_ones, s_zeros
                is_first = False
            else:
                result_ones &= s_ones
                result_zeros &= s_zeros
                    
        return self.__class__(self.bits, result_ones, result_zeros)
    
    def arithmetic_rshift(self, shift_val) -> "TristateBitVector":
        if self.is_empty:
            return self
                
        amounts = self._get_shift_amounts(shift_val)
        if not amounts:
            return self.empty(self.bits)
                
        result_ones, result_zeros = self.mask, self.mask
        is_first = True
        sign_mask = 1 << (self.bits - 1)
            
        for s in amounts:
            if s >= self.bits:
                s = self.bits - 1  # arithmetic shift clamps at (bits - 1)
                    
            s_ones = self.ones >> s
            s_zeros = self.zeros >> s
            high_mask = self.mask & ~(self.mask >> s)
                
            # replicate sign bit if known
            if self.ones & sign_mask:
                s_ones |= high_mask
            elif self.zeros & sign_mask:
                s_zeros |= high_mask
            # if sign bit is unknown, neither high_mask is applied, leaving high bits unknown
                    
            if is_first:
                result_ones, result_zeros = s_ones, s_zeros
                is_first = False
            else:
                result_ones &= s_ones
                result_zeros &= s_zeros
                    
        return self.__class__(self.bits, result_ones, result_zeros)

    # (v1.1.1) fix: here the 0(bitssquare) exec bottleneck is fixed
    def __mul__(self, other) -> "TristateBitVector":
        if self.is_empty:
            return self
    
        if not hasattr(other, "ones"):
            other = self.value(int(other), self.bits)
    
        if other.is_empty:
            return self.empty(self.bits)
    
        if other.ones == 0 and other.zeros == self.mask:
            return self.value(0, self.bits)
    
        result = self.value(0, self.bits)
    
        for i in range(self.bits):
            b_1 = (other.ones >> i) & 1
            b_0 = (other.zeros >> i) & 1
    
            if b_0 and not b_1:
                continue
    
            shifted_self = self << i
    
            if b_1 and not b_0:
                result = result + shifted_self
            else:
                unknown_term = self.__class__(
                    self.bits, ones=0, zeros=shifted_self.zeros
                )
                result = result + unknown_term
    
        return result

    # (v1.1.1)addition: modulo(__mod__) op
    def __mod__(self: "TristateBitVector", other: "TristateBitVector") -> "TristateBitVector":
        if self.is_empty or other.is_empty:
            return self.empty(self.bits)
    
        # modulo by definitively 0 is undefined; return empty matching floordiv behavior
        if other.ones == 0 and other.zeros == self.mask:
            return self.empty(self.bits)

        # fast-pass: both are exact constants
        if self.unknown == 0 and other.unknown == 0:
            return self.__class__.value(self.ones % other.ones, self.bits)
    
        a_min, a_max = self.get_min_max()
        b_min, b_max = other.get_min_max()
            
        # xase 1: self is definitively less than other's minimum -> bits are unmodified
        if b_min > 0 and a_max < b_min:
            return self
    
        # case 2: other is a known constant
        if other.unknown == 0:
            k = other.ones
            # power of 2 optimization -> Modulo is exactly bitwise AND with (k - 1)
            if k > 0 and (k & (k - 1)) == 0:
                mask_tbv = self.value(k - 1, self.bits)
                return self & mask_tbv
    
        # case 3: General upper bound bit-clearing
        max_possible = a_max
        if b_max > 0:
            max_possible = min(a_max, b_max - 1)
                
        # construct a mask of all valid lower bits up to max_possible
        if max_possible == 0:
            valid_mask = 0
        else:
            valid_mask = (1 << max_possible.bit_length()) - 1
                
        # any bit higher than the msb of max_possible must be 0.
        # the lower bits (inside valid_mask) are scrambled and mathematically unknown.
        n_zeros = self.mask & ~valid_mask
        n_ones = 0
                
        return self.__class__(self.bits, n_ones, n_zeros)
