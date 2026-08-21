# Infer JSON

Tool to infer type definitions from JSON data. This is useful for exploring data where schemas don't exist or aren't public. Currently supports TypeScript, Go, and Python

## Installation

Install with `uv tool` or `pipx`

```sh
uv tool install git+https://github.com/jessejenks/infer-json.git
pipx install git+https://github.com/jessejenks/infer-json.git
```

Or clone locally and run with

```sh
uv run -m infer_json ...
python -m infer_json ...
```

## Examples

### Basic

For a simple JSON object, this tool produces the same or similar type as the one TypeScript would infer.

```json
{
    "name": "foo",
    "count": 1,
    "ratio": 3.14,
    "completedAt": null,
    "days": ["Monday", "Wednesday", "Friday"]
}
```

```sh
infer-json examples/basic.json
```

```ts
type Root = {
  name: string;
  count: number;
  ratio: number;
  completedAt: null;
  days: string[];
};
```

And a similar struct definition for Go.

```go
type Root struct {
	Name string `json:"name"`
	Count int `json:"count"`
	Ratio float64 `json:"ratio"`
	CompletedAt any `json:"completedAt"`
	Days []string `json:"days"`
}
```

And a `TypedDict` in Python

```py
Root = TypedDict("Root", {
	"name": str,
	"count": int,
	"ratio": float,
	"completedAt": None,
	"days": list[str],
})
```

### Literal types

By default, the tool does not try to infer literal types, instead treating all strings as `string`.

```jsonl
{ "foo": "a" }
{ "foo": "b" }
```

```sh
infer-json examples/string-literals.jsonl
```

```ts
type Root = {
  foo: string;
};
```

This can be controlled with `-l` or `--max-literals` flag. Note that this *only* applies to strings, not numbers.

```sh
infer-json examples/string-literals.jsonl --max-literals 2
```

```ts
type Root = {
  foo: "a" | "b";
};
```

This means that up to 2 distinct values for the key `"foo"` are kept as literals before falling back to `string`.

Python also supports literal types.

```py
Root = TypedDict("Root", {
	"foo": Literal["a"] | Literal["b"],
})
```

Go does not have any context of literals, so `--max-literals` is ignored and strings are always inferred as `string`

```sh
infer-json examples/string-literals.jsonl --max-literals 2 --output go
```

```go
type Root struct {
	Foo string `json:"foo"`
}
```

### Discriminants

The tool can also try to find a discriminating key for top-level objects.

```jsonl
{ "type": "dog", "bark": true }
{ "type": "dog", "bark": false }
{ "type": "cat", "purr": true }
{ "type": "cat", "lives": 9 }
```

```sh
infer-json examples/discriminating.jsonl
```

```ts
type Variant0 = {
  type: string;
  bark: boolean;
};

type Variant1 = {
  type: string;
  purr: boolean;
};

type Variant2 = {
  type: string;
  lives: number;
};

type Root = Variant0 | Variant1 | Variant2;
```

By using the `-d` or `--find-discriminant` flag, we can get much nicer output.

```sh
infer-json examples/discriminating.jsonl --find-discriminant
```

```ts
type Dog = {
  type: "dog";
  bark: boolean;
};

type Cat = {
  type: "cat";
  purr?: boolean;
  lives?: number;
};

type Root = Dog | Cat;
```

Notice that the discriminating key `"type"` has a literal type even though max literals was 0.

The same can be done in Python.

```py
Dog = TypedDict("Dog", {
	"type": Literal["dog"],
	"bark": bool,
})

Cat = TypedDict("Cat", {
	"type": Literal["cat"],
	"purr": NotRequired[bool],
	"lives": NotRequired[int],
})

type Root = Dog | Cat
```

Optional fields use `NotRequired` for Python.

Since Go does not have any literal types, it also does not have a discriminating key and so `--find-discriminant` is also ignored for go output.

### Nested Objects

Nested objects are treated as separate types.

```json
{
    "foo": "string",
    "nested": {
        "bar": 1
    }
}
```

```sh
infer-json examples/nested.json
```

```ts
type RootNested = {
  bar: number;
};

type Root = {
  foo: string;
  nested: RootNested;
};
```

Similarly for Go and Python.

```go
type RootNested struct {
	Bar int `json:"bar"`
}

type Root struct {
	Foo string `json:"foo"`
	Nested RootNested `json:"nested"`
}
```

```py
RootNested = TypedDict("RootNested", {
	"bar": int,
})

Root = TypedDict("Root", {
	"foo": str,
	"nested": RootNested,
})
```

### Merging Objects

By default, objects are grouped by their keys. So only objects with the exact same keys can be considered the same type.

```jsonl
{ "key1": 1, "key2": 2, "key3": 3 }
{ "key1": 1, "key2": 2, "key3": 3, "key4": 4 }
{ "key1": 1, "key2": 2, "key3": 3, "key5": 5 }
```

```sh
infer-json examples/merge-objects.jsonl
```

```ts
type Variant0 = {
  key1: number;
  key2: number;
  key3: number;
};

type Variant1 = {
  key1: number;
  key2: number;
  key3: number;
  key4: number;
};

type Variant2 = {
  key1: number;
  key2: number;
  key3: number;
  key5: number;
};

type Root = Variant0 | Variant1 | Variant2;
```

And for Python

```py
Variant0 = TypedDict("Variant0", {
	"key1": int,
	"key2": int,
	"key3": int,
})

Variant1 = TypedDict("Variant1", {
	"key1": int,
	"key2": int,
	"key3": int,
	"key4": int,
})

Variant2 = TypedDict("Variant2", {
	"key1": int,
	"key2": int,
	"key3": int,
	"key5": int,
})

type Root = Variant0 | Variant1 | Variant2
```

And for Go

```go
type Variant0 struct {
	Key1 int `json:"key1"`
	Key2 int `json:"key2"`
	Key3 int `json:"key3"`
}

type Variant1 struct {
	Key1 int `json:"key1"`
	Key2 int `json:"key2"`
	Key3 int `json:"key3"`
	Key4 int `json:"key4"`
}

type Variant2 struct {
	Key1 int `json:"key1"`
	Key2 int `json:"key2"`
	Key3 int `json:"key3"`
	Key5 int `json:"key5"`
}

// Root is one of: Variant0, Variant1, Variant2
```

Notice that since Go does not have union types there is no top-level type definition.

Whether record[^1] types should be considered the same type can be controlled with the `-k` or `--min-shared-keys` option.

```sh
infer-json examples/merge-objects.jsonl --min-shared-keys 3
```

This means objects with at least 3 shared keys should be merged.

```ts
type Root = {
  key1: number;
  key2: number;
  key3: number;
  key4?: number;
  key5?: number;
};
```

Similarly for Go and Python

```go
type Root struct {
	Key1 int `json:"key1"`
	Key2 int `json:"key2"`
	Key3 int `json:"key3"`
	Key4 *int `json:"key4,omitempty"`
	Key5 *int `json:"key5,omitempty"`
}
```

```py
Root = TypedDict("Root", {
	"key1": int,
	"key2": int,
	"key3": int,
	"key4": NotRequired[int],
	"key5": NotRequired[int],
})
```

### Map Types

Objects with keys longer than a threshold are inferred as map types (`Record<string, T>` in TypeScript, `map[string]T` in Go, and `dict[str, T]` in Python).

In this example, the first line is a record type, while the second is a map type.

```jsonl
{"enable": false}
{"enable": true, "very-long-key-that-turns-this-into-a-map-type": "cffc1d89-62da-4a08-89e2-e13d85e908a7"}
```

```sh
infer-json examples/map.jsonl
```

```ts
type Variant0 = {
  enable: boolean;
};

type Root = Variant0 | Record<string, boolean | string>;
```

```go
type Variant0 struct {
	Enable bool `json:"enable"`
}

// Root is one of: Variant0, map[string]any
```

```py
Variant0 = TypedDict("Variant0", {
	"enable": bool,
})

type Root = Variant0 | dict[str, bool | str]
```

The `-K` or `--max-key-length` option controls this threshold. Setting it to 0 disables map detection entirely.

```ts
type Variant0 = {
	enable: boolean;
};

type Variant1 = {
	enable: boolean;
	"very-long-key-that-turns-this-into-a-map-type": string;
};

type Root = Variant0 | Variant1;
```

For Go

```go
type Variant0 struct {
	Enable bool `json:"enable"`
}

type Variant1 struct {
	Enable bool `json:"enable"`
	VeryLongKeyThatTurnsThisIntoAMapType string `json:"very-long-key-that-turns-this-into-a-map-type"`
}

// Root is one of: Variant0, Variant1
```

and for Python

```py
Variant0 = TypedDict("Variant0", {
	"enable": bool,
})

Variant1 = TypedDict("Variant1", {
	"enable": bool,
	"very-long-key-that-turns-this-into-a-map-type": str,
})

type Root = Variant0 | Variant1
```

Alternatively, if the `-F` or `--flatten-maps` flag is used, if any top-level object is detected as a map, all top-level objects are flattened into the map type.

```sh
infer-json examples/map.jsonl --flatten-maps
```

```ts
type Root = Record<string, boolean | string>;
```

### Top-Level Arrays

When the input is a JSON array rather than an object, the tool infers the item type and produces an array type for `Root`.

```json
[
    {"foo": "top-level-list"},
    {"foo": "bar", "bar": "baz"}
]
```

```sh
infer-json examples/list.json
```

```ts
type Variant = {
	foo: string;
	bar?: string;
};

type Root = Variant[];
```

And for Go and Python.

```go
type Variant struct {
	Foo string `json:"foo"`
	Bar *string `json:"bar,omitempty"`
}

// Root is: []Variant
```

```py
Variant = TypedDict("Variant", {
	"foo": str,
	"bar": NotRequired[str],
})

type Root = list[Variant]
```

### Multiple Files

The tool accepts multiple files and merges all objects into a single type.

### Comments

The tool supports basic JSONC line comments, but not block comments. Files have comments stripped automatically regardless of the extension.

### Depth

The `-D` or `--max-depth` flag limits how many levels of nested objects are expanded. Objects beyond the limit are collapsed to `unknown`/`any`. The default is 0, meaning no limit. Only record nesting counts toward the depth, not lists.

```sh
infer-json examples/nested.json --max-depth 1
```

```ts
type Root = {
	foo: string;
	nested: unknown;
};
```

### Naming Options

By default, the root type is called `Root`, anonymous variants are numbered `Variant0`, `Variant1`, etc., and discriminant-derived names like `Dog` or `Cat` are used as-is. These can be customized with three independent flags.

Note that provided names are converted to Pascal case and non-alphanumeric characters are removed.

#### `--root`

The `-r` or `--root` flag changes the root type name.

```sh
infer-json examples/basic.json --root Config
```

```ts
type Config = {
	name: string;
	count: number;
	ratio: number;
	completedAt: null;
	days: string[];
};
```

This works with the names generated from discriminated keys as well.

```sh
infer-json examples/discriminating.jsonl --find-discriminant --root Animal
```

```ts
type Dog = {
  type: "dog";
  bark: boolean;
};

type Cat = {
  type: "cat";
  purr?: boolean;
  lives?: number;
};

type Animal = Dog | Cat;
```

#### `--prefix`

The `-p` or `--prefix` flag prepends a string to all generated type names.

```sh
infer-json examples/discriminating.jsonl --find-discriminant --root Animal --prefix My
```

```ts
type MyDog = {
  type: "dog";
  bark: boolean;
};

type MyCat = {
  type: "cat";
  purr?: boolean;
  lives?: number;
};

type MyAnimal = MyDog | MyCat;
```

#### `--variant`

The `--variant` flag changes the word used for anonymous variant types (default `Variant`).

```sh
infer-json examples/merge-objects.jsonl --root Api --variant Case
```

```ts
type Case0 = {
  key1: number;
  key2: number;
  key3: number;
};

type Case1 = {
  key1: number;
  key2: number;
  key3: number;
  key4: number;
};

type Case2 = {
  key1: number;
  key2: number;
  key3: number;
  key5: number;
};

type Api = Case0 | Case1 | Case2;
```

These flags can be combined. For example, `--prefix Response --variant Case` produces `ResponseApi`, `ResponseCase0`, `ResponseCase1`, etc.

### Other Options

- `-L` or `--max-literal-length`: When using `--max-literals`, string literals longer than this are widened to `string`. This prevents long values like UUIDs or URLs from being kept as literals. Set to 0 to disable.
- `--jsonl`: Force all input files to be parsed as JSONL, regardless of file extension.
- `-s` or `--sort-keys`: Sort object keys alphabetically in output.
- `--readonly`: Emit `readonly` fields in TypeScript output. Ignored for Go.
- `--use-spaces`: Use spaces for indentation instead of tabs.
- `--tab-width`: Number of spaces per indentation level (default 2, only used with `--use-spaces`).

## Background

This project grew out of a script I wrote for generating Go structs from JSON API responses. I ran into a similar issue on a TypeScript project and realized this could be a useful project. 

You can see more details about the underling type system in the [typing document](/typing.md)

---

[^1]: In type theory literature, record types as what we would call objects or dictionaries. But this is slightly at odds with TypeScript terminology which uses the `Record` type to mean a generic mapping like `Record<string, number>`. But this distinction is not totally clear because TS allows things like `Record<"a" | "b", number>` which is effectively equivalent to `{"a": number; "b": number}`.
