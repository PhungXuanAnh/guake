- [1. run on local](#1-run-on-local)
  - [1.1. prepare environment](#11-prepare-environment)
  - [1.2. debug](#12-debug)

# 1. run on local

## 1.1. prepare environment

```shell
pyenv local 3.9.0
venv-create

make local-prepare-environment
make local-run
```

## 1.2. debug

1. run guake with debugpy

```shell
make dev-debug
```

2. run debug mode vscode
3. set breakpoints
4. reduce guake windows size, because when debug, guake terminal will stay in screen
5. do something in guake terminale
