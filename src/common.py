class VSADivisionByZero(Exception):
    def __init__(self, message: str, surviving_state: 'CircularStridedInterval'):
        super().__init__(message)
        self.surviving_state = surviving_state

def _exgcd(a: int, b: int) -> tuple[int, int, int]:
    x0, x1, y0, y1 = 1, 0, 0, 1
    while b != 0:
        q, a, b = a // b, b, a % b
        x0, x1 = x1, x0 - q * x1
        y0, y1 = y1, y0 - q * y1
    return a, x0, y0
