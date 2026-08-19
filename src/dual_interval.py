from typing import TYPE_CHECKING
from .intervals import CircularStridedInterval
from .common import VSADivisionByZero

class DualInterval:
    __slots__ = ('bits', 'mask', 'sign_bit', 'u_domain', 's_domain', 'is_empty')

    def __init__(self, u_domain: CircularStridedInterval, s_domain: CircularStridedInterval = None):
        self.bits = u_domain.bits
        self.mask = u_domain.mask
        self.sign_bit = 1 << (self.bits - 1)
        self.is_empty = u_domain.is_empty

        if self.is_empty:
            self.u_domain = u_domain
            self.s_domain = u_domain
            return

        self.u_domain = u_domain
                                                                                    
        if s_domain is None:
            self.s_domain = self._shift_domain(self.u_domain, self.sign_bit)
        else:
            self.s_domain = s_domain

    @classmethod
    def empty(cls, bits: int = 32) -> 'DualInterval':
        return cls(CircularStridedInterval.empty(bits))

    @classmethod
    def top(cls, bits: int = 32) -> 'DualInterval':
        return cls(CircularStridedInterval.top(bits))

    @classmethod
    def value(cls, val: int, bits: int = 32) -> 'DualInterval':
        u_val = CircularStridedInterval.value(val, bits)
        return cls(u_val)

    def _shift_domain(self, domain: CircularStridedInterval, offset: int) -> CircularStridedInterval:
        if domain.is_empty:
            return domain
        n_lower = (domain.lower + offset) & self.mask
        n_upper = (domain.upper + offset) & self.mask
        return domain.__class__(domain.stride, n_lower, n_upper, self.bits)

    def _synchronize(self) -> 'DualInterval':
        if self.u_domain.is_empty or self.s_domain.is_empty:
            return self.empty(self.bits)
                                        
        s_as_u = self._shift_domain(self.s_domain, self.sign_bit)
                                                      
        refined_u = self.u_domain.intersect(s_as_u)
        
        if refined_u.is_empty:
            return self.empty(self.bits)
                                                                              
        refined_s = self._shift_domain(refined_u, self.sign_bit)
        
        return DualInterval(refined_u, refined_s)
                                                                                                                                                        
    def __add__(self, other: 'DualInterval') -> 'DualInterval':
        if self.is_empty or other.is_empty: return self.empty(self.bits)
                                                                            
        res_u = self.u_domain + other.u_domain
        res_s = self.s_domain + other.s_domain
        
        return DualInterval(res_u, res_s)._synchronize()

    def __sub__(self, other: 'DualInterval') -> 'DualInterval':
        if self.is_empty or other.is_empty: return self.empty(self.bits)
        
        res_u = self.u_domain - other.u_domain
        res_s = self.s_domain - other.s_domain
        
        return DualInterval(res_u, res_s)._synchronize()

    def __mul__(self, other: 'DualInterval') -> 'DualInterval':
        if self.is_empty or other.is_empty: return self.empty(self.bits)
        
        res_u = self.u_domain * other.u_domain
                                                                 
        res_s = self.s_domain * other.s_domain
        
        return DualInterval(res_u, res_s)._synchronize()                                                                                                                           
                                                                        
    def __floordiv__(self, other: 'DualInterval') -> 'DualInterval':
        if self.is_empty or other.is_empty: return self.empty(self.bits)
        
        try:
                                                          
            res_u = self.u_domain // other.u_domain
            return DualInterval(res_u)._synchronize()
        except VSADivisionByZero as e:
                                                                     
            surviving = DualInterval(e.surviving_state)._synchronize()
            raise VSADivisionByZero(e.args[0], surviving)

    def signed_floordiv(self, other: 'DualInterval') -> 'DualInterval':
        if self.is_empty or other.is_empty: return self.empty(self.bits)
        
        try:                                                                                                                                                                           
            res_u = self.u_domain.signed_floordiv(other.u_domain)
            res_s = self.s_domain.signed_floordiv(other.s_domain)
            return DualInterval(res_u)._synchronize()
        except VSADivisionByZero as e:
            surviving = DualInterval(e.surviving_state)._synchronize()
            raise VSADivisionByZero(e.args[0], surviving)
                                                                                                                                                                 
    def __and__(self, other: 'DualInterval') -> 'DualInterval':
        if self.is_empty or other.is_empty: return self.empty(self.bits)
        res_u = self.u_domain & other.u_domain
        return DualInterval(res_u)._synchronize()

    def __or__(self, other: 'DualInterval') -> 'DualInterval':
        if self.is_empty or other.is_empty: return self.empty(self.bits)
        res_u = self.u_domain | other.u_domain
        return DualInterval(res_u)._synchronize()

    def __xor__(self, other: 'DualInterval') -> 'DualInterval':
        if self.is_empty or other.is_empty: return self.empty(self.bits)
        res_u = self.u_domain ^ other.u_domain
        return DualInterval(res_u)._synchronize()
                                                                                                                                                                              
    def union(self, other: 'DualInterval') -> 'DualInterval':
        if self.is_empty: return other
        if other.is_empty: return self
        
        res_u = self.u_domain.union(other.u_domain)
        res_s = self.s_domain.union(other.s_domain)
        
        return DualInterval(res_u, res_s)._synchronize()

    def intersect(self, other: 'DualInterval') -> 'DualInterval':
        if self.is_empty or other.is_empty: return self.empty(self.bits)
        
        res_u = self.u_domain.intersect(other.u_domain)
        res_s = self.s_domain.intersect(other.s_domain)
        
        return DualInterval(res_u, res_s)._synchronize()

    def widen(self, other: 'DualInterval', thresholds: list[int] = None) -> 'DualInterval':
        if self.is_empty: return other
        if other.is_empty: return self
                                                                                                                                                                
        res_u = self.u_domain.widen(other.u_domain, thresholds)
                                                          
        s_thresholds = None
        if thresholds:
            s_thresholds = [(t + self.sign_bit) & self.mask for t in thresholds]
            
        res_s = self.s_domain.widen(other.s_domain, s_thresholds)
        
        return DualInterval(res_u, res_s)._synchronize()

    def narrow(self, other: 'DualInterval') -> 'DualInterval':
        if self.is_empty or other.is_empty: 
            return self.empty(self.bits)
                                                  
        res_u = self.u_domain.narrow(other.u_domain)
        res_s = self.s_domain.narrow(other.s_domain)
            
        return DualInterval(res_u, res_s)._synchronize()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DualInterval): return False
        if self.is_empty and other.is_empty: return True
                                                                                        
        return self.u_domain == other.u_domain

    def __repr__(self):
        if self.is_empty: return "⊥"
                                                                                          
        return f"Dual({self.u_domain.__repr__()})"
