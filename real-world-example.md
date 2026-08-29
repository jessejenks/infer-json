# Real-World Example: Public APIs

## PokeAPI Berries

The [PokeAPI](https://pokeapi.co) berry endpoint returns objects with nested structures.

```sh
for i in {1..68}; do
  curl -s "https://pokeapi.co/api/v2/berry/$i" -o "berry-$i.json"
done
infer-json berry-*.json --root Berry
```

```ts
type BerryFirmness = {
	name: string;
	url: string;
};

type BerryFlavorsFlavor = {
	name: string;
	url: string;
};

type BerryFlavors = {
	potency: number;
	flavor: BerryFlavorsFlavor;
};

type BerryItem = {
	name: string;
	url: string;
};

type BerryNaturalGiftType = {
	name: string;
	url: string;
};

type Berry = {
	id: number;
	name: string;
	growth_time: number | null;
	max_harvest: number | null;
	natural_gift_power: number | null;
	size: number | null;
	smoothness: number | null;
	soil_dryness: number | null;
	firmness: BerryFirmness | null;
	flavors: BerryFlavors[];
	item: BerryItem;
	natural_gift_type: BerryNaturalGiftType | null;
};
```

### Comparison with the Schema

The PokeAPI publishes an [OpenAPI spec](https://raw.githubusercontent.com/PokeAPI/pokeapi/master/openapi.yml). Comparing against the `BerryDetail` schema:

- `firmness`, `item`, `natural_gift_type` are correctly inferred as `{name: string, url: string}`
- `flavors` is correctly inferred as an array of `{potency: number, flavor: {name, url}}`
- The schema defines `growth_time`, `max_harvest`, `size`, `smoothness`, `soil_dryness`, and `natural_gift_power` as `integer | null`.
- The schema uses distinct named types (`BerryFirmnessSummary`, `ItemSummary`, etc.) for structurally identical `{name, url}` objects. The tool names types by position instead (e.g. `BerryFirmness`, `BerryItem`) since it can't infer semantic distinctions from data alone.


It's very important to note that this tool was **only** able to infer `number | null` because it pulled enough examples to see that the field was nullable.

If we were to only run again say the first 10 berry types, we would get this output instead.

```ts
type Root = {
	id: number;
	name: string;
	growth_time: number;
	max_harvest: number;
	natural_gift_power: number;
	size: number;
	smoothness: number;
	soil_dryness: number;
	firmness: RootFirmness;
	flavors: RootFlavors[];
	item: RootItem;
	natural_gift_type: RootNaturalGiftType;
};
```

## GitHub Events

The [GitHub Events API](https://docs.github.com/en/rest/activity/events) returns objects with a `type` field identifying the event kind. Each type has a different `payload` structure — see the [GitHub OpenAPI spec](https://github.com/github/rest-api-description). But every event shares the same *top-level* keys; the structural variation is nested inside `payload`.

A semi-anonymized snapshot is included at `examples/github-events.jsonl`.

```sh
curl -s "https://api.github.com/repos/python/cpython/events?per_page=10" \
  | python3 -c "import sys,json; [print(json.dumps(x)) for x in json.load(sys.stdin)]" \
  > examples/github-events.jsonl
```

Without `--find-discriminant`, all events merge into one type with every payload field optional:

```sh
infer-json examples/github-events.jsonl --root Event --max-depth 2
```

```ts
type EventActor = {
	id: number;
	login: string;
	display_login: string;
	gravatar_id: string;
	url: string;
	avatar_url: string;
};

type EventRepo = {
	id: number;
	name: string;
	url: string;
};

type EventPayload = {
	action?: string;
	number?: number;
	pull_request?: unknown;
	label?: unknown;
	labels?: unknown[];
	review?: unknown;
	issue?: unknown;
	repository_id?: number;
	push_id?: number;
	ref?: string;
	head?: string;
	before?: string;
};

type EventOrg = {
	id: number;
	login: string;
	gravatar_id: string;
	url: string;
	avatar_url: string;
};

type Event = {
	id: string;
	type: string;
	actor: EventActor;
	repo: EventRepo;
	payload: EventPayload;
	public: boolean;
	created_at: string;
	org: EventOrg;
};
```

With the flag, the tool detects that `type` correlates with structural differences in `payload` and splits accordingly:

```sh
infer-json examples/github-events.jsonl --root Event --find-discriminant --max-depth 2
```

```ts
type PullRequestEventActor = {
	id: number;
	login: string;
	display_login: string;
	gravatar_id: string;
	url: string;
	avatar_url: string;
};

type PullRequestEventRepo = {
	id: number;
	name: string;
	url: string;
};

type PullRequestEventPayload = {
	action: string;
	number: number;
	pull_request: unknown;
	label?: unknown;
	labels?: unknown[];
};

type PullRequestEventOrg = {
	id: number;
	login: string;
	gravatar_id: string;
	url: string;
	avatar_url: string;
};

type PullRequestEvent = {
	id: string;
	type: "PullRequestEvent";
	actor: PullRequestEventActor;
	repo: PullRequestEventRepo;
	payload: PullRequestEventPayload;
	public: boolean;
	created_at: string;
	org: PullRequestEventOrg;
};

/* ... */

type PullRequestReviewEvent = {
	id: string;
	type: "PullRequestReviewEvent";
	actor: PullRequestReviewEventActor;
	repo: PullRequestReviewEventRepo;
	payload: PullRequestReviewEventPayload;
	public: boolean;
	created_at: string;
	org: PullRequestReviewEventOrg;
};

/* ... */

type WatchEvent = {
	id: string;
	type: "WatchEvent";
	actor: WatchEventActor;
	repo: WatchEventRepo;
	payload: WatchEventPayload;
	public: boolean;
	created_at: string;
	org: WatchEventOrg;
};

/* ... */

type IssuesEvent = {
	id: string;
	type: "IssuesEvent";
	actor: IssuesEventActor;
	repo: IssuesEventRepo;
	payload: IssuesEventPayload;
	public: boolean;
	created_at: string;
	org: IssuesEventOrg;
};

/* ... */

type PushEvent = {
	id: string;
	type: "PushEvent";
	actor: PushEventActor;
	repo: PushEventRepo;
	payload: PushEventPayload;
	public: boolean;
	created_at: string;
	org: PushEventOrg;
};

type Event = PullRequestEvent | PullRequestReviewEvent | WatchEvent | IssuesEvent | PushEvent;
```

Each variant gets a literal `type` field and its own payload type and sub-types. Records that share the same discriminant value are merged.
