# Typing

The type theory underlying this tool

Because JSON is so simple, the actual type inference is very straightforward. The complexity comes from merging types.

## Types

Our basic types are

```
unknown
null
boolean
int
float
string literal
string
list
map
record
union
```

The `unknown` type is intended to represent cases like `{"key": []}` where we don't know the intended type.

We rely on some basic subtyping rules. For instance `int ≤ float` and `"a" ≤ string`. We also use *covariant* typing for lists, so `int[] ≤ float[]`. This may be surprising since lists are usually *contravariant* in programming languages. But that is usually about function parameters.

## Rules

Here, `T`, `S`, `U`, and `V` are arbitrary types
And `A` and `B` are non-union types
`"a"` and `"b"` represent string literals

subtype ordering

```plain
            T ≤ T
            T ≤ V             if T ≤ U and U ≤ V
            T ≤ T | S
            T ≤ S | T
      unknown ≤ T
          int ≤ float
      literal ≤ string
       List T ≤ List S        if T ≤ S
      Map[K]T ≤ Map[K]S       if T ≤ S
           {} ≤ {k?: S}
      {k : T} ≤ {k : S}       if T ≤ S
      {k : T} ≤ {k?: S}       ''
      {k?: T} ≤ {k?: S}       ''
A1 | ... | An ≤ T             if forall i, Ai ≤ T
            A ≤ B1 | ... | Bm if exists j,  A ≤ Bj
```

Our corresponding joins/merge satisfies the usual condition `A ≤ B` iff `A | B = B`.

```plain
      T | T       = T
      T | S       = S | T
(T | S) | U       = T | (S | U)
unknown | T       = T
    int | float   = float
    "a" | string  = string
 List T | List S  = List (T | S)
Map[K]T | Map[K]S = Map[K](T | S)
     {} | {k : S} = {k?: S}
     {} | {k?: S} = {k?: S}
{k : T} | {k : S} = {k : T | S}
{k : T} | {k?: S} = {k?: T | S}
{k?: T} | {k?: S} = {k?: T | S}
```

## Notes

We treat `unknown` as a bottom type. This is slightly at odds with the `go` output, since we emit `any`, which is a top type.

For records with multiple keys, the rules are point-wise, using `{} ≤ {k?: unknown} ≤ {k?: S}` for missing keys. This implies that every key missing on the left hand side must be optional on the right hand side.

This is slightly unusual, normally we would want width subtyping, where `{x: int, y: string} ≤ {x: int}`. But for our purposes, this would mean `{x: int, y: string} | {x: int} = {x: int}`, which drops `y` entirely. Instead we want `{x: int, y: string} | {x: int} = {x: int, y?: string}`. Which is why our rule is `{} ≤ {k?: T}` since `{y?: string} | {} = {y?: string}`.

Notice that this also implies `{k: T} ≰ {}` when `T ≠ unknown` since this would require `{k: T} ≤ {} ≤ {k?: unknown}`, but `T ≰ unknown`.
