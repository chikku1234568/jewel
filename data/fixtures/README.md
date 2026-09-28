# Test fixtures

For automated tests and local development only. **Never inserted into a new account**,
and not a demo mode in the interface: a new account starts with an empty library.

## Two short text documents

| # | Document date | Text |
|---|---|---|
| 1 | January | "The warehouse key is held by Sam. The alarm code is 4412." |
| 2 | March | "The alarm code was rotated after the break-in." |

Document 2 does not contain "Sam" or "4412".

## What later tests should show

- A graph question about whether the alarm code is still 4412 can reach the March
  document through the shared alarm-code entity.
- A text-chunk search for "4412" ranks the January document and can miss the March one.

The fixture files themselves (for example `warehouse-january.txt`,
`warehouse-march.txt`) will be added with the first test that uses them.
