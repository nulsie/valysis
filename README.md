valysis - a VSA library for Python

There is a distinct lack of dedicated VSA(Value Set Analysis) libraries in Python, like literally, there is none. You woud say that
there are things like Angr, but they are not dedicated for VSA, but as large frameworks for building or basing entire RE tools, As i was
trying to make a IR(Intermediate Representation) based static analysis RE tool in Python a while ago, i found the issue, and as it is commonly known,
creating entire VSA engines and CFGs from scratch are notoriously difficult if not impossible and litearly there was no dedicated VSA library
available. So i made an entire fully functional precision-focused library dedicated just for VSA from scratch and arguably the first in Python, and that is *valysis*.

valysis is decoupled from any specific instruction set architecture or Intermediate Representation (IR). It provides a sound, flexible backend domain engine which is superior in precision rate than Angr(from the tests I've done in a short-term)^^ that can be attached to 
Ghidra PCODE, IDA Microcode, Triton ASTs, Binary Ninja LLIL/MLIL, or custom emulation lifters. To preserve precision across mixed
arithmetic-bitwise code, the lib combines Circular Strided Interval(better than the usual standard of using the less precision-focused Strided Interval) with Tristate BitVectors via mutual reduction. Then it natively supports arbitrary bit-widths (8, 16, 32, 64, 128bits) per variable.
And also accurately tracks `signed` and `unsigned` ranges bit-by-bit which eliminates domain divergence under signed and unsigned branch conditions(more on this is discussed below*).
The memory modeling handles pointers and mem regions quite well tuned for practical usage(and was a pain to write)^. And as is a inherent quality of life with static analysis, valysis is hardware/software agnostic.
valysis also keeps exact discrete sets for small cardinalities before widening to abstract domains (ideal for jump tables and flag sets).

And IMO the best thing outta all about this is that, valysis is completely external deps-free, as almost everything was written from scratch(the only dep used being the prepackaged `math` lib)
And also you should know that valysis only deals with VSA and nothing else like the lifters or CFG(you have to DIY, as the point of this lib is to build a VSA-dedicated lib)


```

+-----------------------------------------------------------------------+
|                        Target Lifter / Engine                         |
|               (e.g., Ghidra PCODE / IDA Microcode / IR)               |
+-----------------------------------------------------------------------+
|
v
+-----------------------------------------------------------------------+
|                           Memory State & ValueSets                    |
|  - Tracks value mappings across multiple MemoryRegions                |
|  - Manages byte-level serialization / endianness / strong & weak updates|
+-----------------------------------------------------------------------+
|
v
+-----------------------------------------------------------------------+
|                            HybridSetDomain                            |
|  - If cardinality <= K (e.g., 8): Track exact discrete value set      |
|  - If cardinality > K: Widens automatically to VSAReducedState        |
+-----------------------------------------------------------------------+
|
v
+-----------------------------------------------------------------------+
|                       VSAReducedState (Product)                       |
|  - Synchronizes CircularStridedInterval and TristateBitVector         |
|  - Executes mutual reduction via `_reduce()` to tighten upper/lower bounds|
+-----------------------------------------------------------------------+
/                                   

v                                     v
+-------------------------------+     +---------------------------------+
| CircularStridedInterval (CSI) |     |     TristateBitVector (TBV)     |
| - Stride, Lower, Upper bounds |     | - Known 1s, Known 0s, Unknowns  |
| - Extended GCD intersections  |     | - Bitwise AND, OR, XOR, Shifts  |
| - Modular arithmetic wrapping |     | - Bounds derivation for product |
+-------------------------------+     +---------------------------------+

```

Functioning of valysis

*it achieves this by pairing two dedicated components rather than relying on a single domain:

Bit-by-bit tracking done by `TristateBitVector`

Bit-level accuracy is handled by tracking individual bits using two explicit bitmasks: ones and zeros. Every bit position is tracked as a known 1, a known 0, or unknown (?). This preserves exact bitwise state across AND, OR, XOR, and shift operations without immediately degrading to broad numeric ranges.

Signed & Unsigned Domain Tracking by `DualInterval`

Signed versus unsigned range tracking is handled by maintaining both an unsigned domain (`u_domain`) and a signed domain (`s_domain`) simultaneously. Instead of picking one representation and losing precision during signed/unsigned comparisons, the `_synchronize()` method shifts domain bounds by the sign bit to cross-refine both contexts.

^ *Strong vs. Weak Updates*: You correctly attempt strong updates only when a pointer resolves to a single, unambiguous concrete offset within a `MemoryRegion`.

*Endianness Support*: The store and load functions respect endianness by properly extracting and concatenating byte-sized slices.

*Safety Net*: If a memory access points to an unknown offset, it safely degrade the read to a topological maximum (`CircularStridedInterval.top` and `TristateBitVector.top`).

Mathematically speaking, these is the processes or theories implemented in the lib:

1. Circular Strided Interval (CSI)

A Circular Strided Interval over $b$-bit modular arithmetic is defined as:

$$s[l, u]_{2^b}$$

Where $s$ is the stride, $l$ is the lower bound, $u$ is the upper bound, and all operations wrap modulo $M = 2^b$. The set of values represented by $s[l, u]$ is:

$$\gamma(s[l, u]) = \{ (l + k \cdot s) \pmod{2^b} \mid 0 \le k \le \lfloor ((u - l) \pmod{2^b}) / s \rfloor \}$$

Wrapped Intervals & Splitting

When $l > u$, the interval wraps around zero. To perform non-modular operations safely (like division or multiplication), the wrapped interval is split into two contiguous linear components:

$$\mathrm{split}(s[l, u]) = \{ s[l, \mathrm{first\_upper}], s[\mathrm{second\_lower}, u] \}$$

Intersection via Extended Euclidean Algorithm

To compute the intersection of two strided intervals $s_1[l_1, u_1]$ and $s_2[l_2, u_2]$, the engine solves the linear congruence equation for common points:

$$l_1 + x \cdot s_1 \equiv l_2 + y \cdot s_2 \pmod{2^b}$$

Using the Extended GCD algorithm:

$$g = \gcd(s_1, s_2) = x_0 s_1 + y_0 s_2$$

A solution exists if and only if $(l_2 - l_1) \pmod g = 0$. The resulting combined stride is the least common multiple:

$$s_{\mathrm{lcm}} = \frac{s_1 \cdot s_2}{\gcd(s_1, s_2)}$$

2. Tristate BitVector (Known-Bits)

The `TristateBitVector` tracks the state of every individual bit in a $b$-bit vector using two integer masks: `ones` ($v_{\mathrm{ones}}$) and `zeros` ($v_{\mathrm{zeros}}$).

* **Known 1**: Bit $i$ has $v_{\mathrm{ones}}[i] = 1, v_{\mathrm{zeros}}[i] = 0$
* **Known 0**: Bit $i$ has $v_{\mathrm{ones}}[i] = 0, v_{\mathrm{zeros}}[i] = 1$
* **Unknown (?)**: Bit $i$ has $v_{\mathrm{ones}}[i] = 0, v_{\mathrm{zeros}}[i] = 0$

Domain Invariant

$$v_{\mathrm{ones}} \land v_{\mathrm{zeros}} = 0$$

If $v_{\mathrm{ones}} \land v_{\mathrm{zeros}} \neq 0$, the domain state is empty ($\bot$).

Bounds Extraction

Minimum and maximum integer values bounded by a tristate vector are derived directly:

$$\mathrm{min\_val} = v_{\mathrm{ones}}$$

$$\mathrm{max\_val} = v_{\mathrm{ones}} \mid (\sim(v_{\mathrm{ones}} \mid v_{\mathrm{zeros}}) \land (2^b - 1))$$

3. Reduced Product Reduction Method

The reduced product domain $\mathcal{D}_{\mathrm{reduced}} = \mathrm{CSI} \times \mathrm{Tristate}$ executes reduction (`_reduce()`) to maintain maximal precision:

$$\mathrm{reduce}(\langle \mathrm{CSI}, \mathrm{Tristate} \rangle) \to \langle \mathrm{CSI}', \mathrm{Tristate}' \rangle$$

1. **Tristate Bounds $\to$ CSI**:

$$l' = \max(l, \mathrm{tri\_min}), \quad u' = \min(u, \mathrm{tri\_max})$$

Bounds are aligned to the stride $s$:

$$l'' = l' + ((s - (l' - l) \pmod s) \pmod s)$$

2. **CSI Alignment $\to$ Tristate**:
If stride $s = 2^k$, the lowest $k$ bits must be zero:

$$v_{\mathrm{zeros}}' = v_{\mathrm{zeros}} \mid (2^k - 1)$$

3. **CSI Equivalences $\to$ Tristate**:
If $l == u$, all bits are known:

$$v_{\mathrm{ones}}' = v_{\mathrm{ones}} \mid l, \quad v_{\mathrm{zeros}}' = v_{\mathrm{zeros}} \mid (\sim l \land \mathrm{mask})$$

If you're choosing valysis, you might want:

1. **Native Bitwise Precision**: Standard interval analysis suffers from over-approximation on operations like `x & 0xFFFFFFF0` or `x | 0x03`. valysis’s reduced product continuously tightens bounds during bitwise manipulation.
2. **Easy Lifter Integration**: Plug valysis directly into Ghidra PCODE or IDA Microcode analysis plugins without setting up complex binary lifting environments.
3. **Deterministic Abstract Execution**: Fast execution with direct arithmetic semantics, eliminating solver overhead.
4. **Vulnerability Analysis Ready**: Features explicit hooks for division-by-zero detection (`VSADivisionByZero`), carrying surviving abstract states to allow paths to fork correctly upon partial zero-division.

^^why & how it outperforms angr in precision

* angr's strided intervals track numbers as $s[l, u]$. When performing a bitwise operation like x & 0x00FF0000, intervals collapse because bit-masking disrupts contiguous range bounds. angr must widen the stride or convert the value into an unconstrained range $[0, 0xFFFFFFFF]$, while
the Reduced Product Domain ($\mathrm{CSI} \times \mathrm{TBV}$) of valysis executes bitwise operations natively in the TristateBitVector domain ($\mathrm{TBV}$) without losing known bits. The reduction operator $\rho$ then projects these known bits back into the CircularStridedInterval ($\mathrm{CSI}$) to re-tighten the lower and upper numeric bounds. 
* In angr, comparing signed values across the sign-bit boundary ($2^{b-1}$) causes standard unsigned intervals to span the entire integer space while valysis's DualInterval maintains an unsigned interval $\mathcal{U}$ and a shifted signed interval $\mathcal{S}$ in parallel. Whenever a branch constraint is evaluated, the result is computed in the optimal domain and propagated to the other domain via the bijection:

$$\mathcal{U}_{\mathrm{refined}} = \mathcal{U} \sqcap \mathrm{shift}(\mathcal{S}, 2^{b-1})$$

* angr's aggressive over-approximation forces small jump tables (e.g., switch cases targeting offsets 0x10, 0x20, 0x30) into a single wide interval $16[16, 48]$ that includes non-existent targets like 0x28 while valysis defers abstraction by keeping precise discrete sets $\{0x10, 0x20, 0x30\}$ until set cardinality exceeds a threshold ($k=8$), ensuring $100\%$ precision on control flow dispatches. 

so if you don't want the entire heavy angr lib and just want a library to handle just the VSA with better precision, valysis might be your best bet in Python.

*Note: and obviously because i focused on precision, there is a  noticable issue with performance ovehead, but this would surely be addressed in the coming updates*

installing it:

pip:

```bash
pip install valysis

```

GIT clone:

Codeberg:

```bash
git clone [https://codeberg.org/nulsie/valysis.git](https://codeberg.org/nulsie/valysis.git)

```

GitHub:

```bash
git clone [https://github.com/nulsie/valyssis.git](https://github.com/nulsie/valyssis.git)

```

ON BUG REPORTING:

There is currently performance issues and  resource overhead with the lib and as this is the first version, there will be bugs for sure: the performance issues will surely be fixed in later versions and is aready in development, if you find any bugs, be sure to [contact](https://nulsie.mywire.org) me so i can discover them faster and push update real-quick.

references & acknowledgments

* **Hacker's Delight (2nd Edition)** by Henry S. Warren, Jr. — The bitwise bounds algorithms for bitwise `AND` and `OR` operations (`_hd_min_and`, `_hd_max_and`, `_hd_min_or`, `_hd_max_or`) used in `CircularStridedInterval` are based on the logical operations theorems in Chapter 4.
* **G. Balakrishnan and T. Reps** — *Analyzing Memory Accesses in x86 Executables* (The foundational paper introducing Value Set Analysis and Circular Strided Intervals).

---

author: nulsie license: MIT
