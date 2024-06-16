# Tanda Runner

A nice description

## Development

Note: We use [uv](https://github.com/astral-sh/uv?tab=readme-ov-file#getting-started) for installing things, make sure you have it.

1. Make sure you are running in a virtual environment (e.g., `python3 -m venv .env`)
2. Activate it (e.g. `source .env/bin/activate`)

```shell
(.env) $ make install-dev
```

3. Run the tests

```shell
(.env) $ make test
```

4. Run the API

```shell
(.env) $ make api
```

5. For more help:
```shell
(.env) $ make help
```

## TODO 

- [x] Chat send on enter
- [x] Loading on send
- [x] Clear conversation
- [x] Cannot chat if not logged in 
- [x] If not logged in, see the charts from Duarte 
- [x] Cache fetching using diskcache for long computations
- [ ] Deployment
- [ ] Small description of the app
- [ ] Logout button
