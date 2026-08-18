# Infer JSON

Tool to infer type definitions from JSON data. This is useful for exploring data where schemas don't exist or aren't public. Currently supports TypeScript and Go.

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

```sh
infer-json examples/basic.jsonl --output go
```

```go
type Root struct {
	Name string `json:"name"`
	Count int `json:"count"`
	Ratio float64 `json:"ratio"`
	CompletedAt any `json:"completedAt"`
	Days []string `json:"days"`
}
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

This can be controlled with `--max-literals` flag. Note that this *only* applies to strings, not numbers.

```sh
infer-json examples/string-literals.jsonl --max-literals 2
```

```ts
type Root = {
  foo: "a" | "b";
};
```

This means that up to 2 distinct values for the key `"foo"` are kept as literals before falling back to `string`.

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

Notice that the discriminating key `"type"` is a literal type even though max literals was 0.

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

And for Go:

```sh
infer-json examples/nested.json --output go
```

```go
type RootNested struct {
	Bar int `json:"bar"`
}

type Root struct {
	Foo string `json:"foo"`
	Nested RootNested `json:"nested"`
}
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

And for Go:

```sh
infer-json examples/merge-objects.jsonl --output go
```

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

This can be controlled with the `-k` or `--min-shared-keys` option.

```sh
infer-json examples/merge-objects.jsonl --min-shared-keys 3
```

```ts
type Root = {
  key1: number;
  key2: number;
  key3: number;
  key4?: number;
  key5?: number;
};
```

And for Go:

```sh
infer-json examples/merge-objects.jsonl --min-shared-keys 3 --output go
```

```go
type Root struct {
	Key1 int `json:"key1"`
	Key2 int `json:"key2"`
	Key3 int `json:"key3"`
	Key4 *int `json:"key4,omitempty"`
	Key5 *int `json:"key5,omitempty"`
}
```

This means objects with at least 3 shared keys should be merged.

### Map Types

Objects with keys longer than a threshold are inferred as map types (`Record<string, T>` in TypeScript, `map[string]T` in Go).

```jsonl
{"enable": true, "very-long-key-that-turns-this-into-a-map-type": "cffc1d89-62da-4a08-89e2-e13d85e908a7"}
{"enable": false}
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

And for Go:

```sh
infer-json examples/map.jsonl --output go
```

```go
type Variant0 struct {
	Enable bool `json:"enable"`
}

// Root is one of: Variant0, map[string]any
```

The `-K` or `--max-key-length` option controls this threshold. Setting it to 0 disables map detection entirely.

With the `-F` or `--flatten-maps` flag, if any top-level object is detected as a map, all top-level objects are flattened into the map type.

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
type RootItem = {
  foo: string;
  bar?: string;
};

type Root = RootItem[];
```

And for Go:

```sh
infer-json examples/list.json --output go
```

```go
type RootItem struct {
	Foo string `json:"foo"`
	Bar *string `json:"bar,omitempty"`
}

// Root is []RootItem
```

### Multiple Files

The tool accepts multiple files and merges all objects into a single type.

### Comments

The tool supports JSONC files (JSON with comments). Files with the `.jsonc` extension are parsed with comments stripped automatically.

### Other Options

- `-L` or `--max-literal-length`: When using `--max-literals`, string literals longer than this are widened to `string`. This prevents long values like UUIDs or URLs from being kept as literals. Set to 0 to disable.
- `--jsonl`: Force all input files to be parsed as JSONL, regardless of file extension.

## Background

This project grew out of a script I wrote for generating Go structs from JSON API responses. I ran into a similar issue on a TypeScript project and realized this could be a useful project. 

You can see more details about the underling type system in the [typing document](/typing.md)
