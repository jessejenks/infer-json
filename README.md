# Infer JSON

Tool to infer TypeScript types from JSON data. This is useful for exploring data where schemas don't exist or aren't public.

## Examples

### Basic

For a simple JSON object, this tool produces a the same or similar type as the one TypeScript would infer.

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
python -m infer_json examples/basic.jsonl
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

### Literal types

By default, the tool does not try to infer literal types, instead treating all strings as `string`.

```jsonl
{ "foo": "a" }
{ "foo": "b" }
```

```sh
python -m infer_json examples/string-literals.jsonl
```

```ts
type Root = {
  foo: string;
};
```

This can be controlled with `--max-literals` flag. Note that this *only* applies to strings, not numbers.

```sh
python -m infer_json examples/string-literals.jsonl --max-literals 2
```

```ts
type Root = {
  foo: "a" | "b";
};
```

This means that up to 2 distinct values for the key `"foo"` are kept as literals before falling back to `string`.


### Discriminants

The tool can also try to find a discriminating key for top-level objects.

```jsonl
{ "type": "dog", "bark": true }
{ "type": "dog", "bark": false }
{ "type": "cat", "purr": true }
{ "type": "cat", "lives": 9 }
```

```sh
python -m infer_json examples/discriminating.jsonl
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
python -m infer_json examples/discriminating.jsonl --find-discriminant
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
python -m infer_json examples/nested.json
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

### Merging Objects

By default, objects are grouped by their keys. So only objects with the exact same keys can be considered the same type.

```jsonl
{ "key1": 1, "key2": 2, "key3": 3 }
{ "key1": 1, "key2": 2, "key3": 3, "key4": 4 }
{ "key1": 1, "key2": 2, "key3": 3, "key5": 5 }
```

```sh
python -m infer_json examples/merge-objects.jsonl
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

This can be controlled with the `-k` or `--min-shared-keys` option.

```sh
python -m infer_json examples/merge-objects.jsonl --min-shared-keys 3
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

This means objects with at least 3 shared keys should be merged.


## Background

This project grew out of a script I wrote for generating Go structs from JSON API responses. I ran into a similar issue on a TypeScript project and realized this could be a useful project.

This is actually a lot harder in TS because of the flexibility of the type system. Possible future work is supporting output in multiple languages. But that would be a pretty big change to the inference logic.
