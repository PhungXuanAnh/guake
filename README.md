- [1. debug on local](#1-debug-on-local)
  - [1.1. prepare environment](#11-prepare-environment)
  - [1.2. step to debug](#12-step-to-debug)

# 1. debug on local

## 1.1. prepare environment

```shell
make dev-without-ln
source .venv/bin/activate
pip install requirement-local.txt
```

## 1.2. step to debug

1. run guake with debugpy

```shell
make dev-debug
```

2. run debug mode vscode
3. set breakpoints
4. reduce guake windows size, because when debug, guake terminal will stay in screen
5. do something in guake terminale
