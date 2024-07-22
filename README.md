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

4. Run the Web App

```shell
(.env) $ make app
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
- [x] Small description of the app
- [x] Logout button
- [x] Deployment
- [x] Adjust weekly running graph for no cut out
- [x] Cleaner rolling tanda chart
- [x] Make sure no cutoffs when openning on laptop
- [x] Adjust progression graph, so you can actually see progression...
- [x] Yearly distance stats
- [x] GitHub style running consistency graph
- [x] Build insights generation pipeline (on login/page render)
- [x] Better experience on mobile
- [x] Ship that shit.
