- [1. run on local](#1-run-on-local)
  - [1.1. prepare environment](#11-prepare-environment)
  - [1.2. debug](#12-debug)
- [2. How to use "mapping path then opening in vscode feature"](#2-how-to-use-mapping-path-then-opening-in-vscode-feature)
- [3. change stk css style](#3-change-stk-css-style)
  - [3.1. css file localtion](#31-css-file-localtion)
  - [3.2. using GTK Inspector for debug css](#32-using-gtk-inspector-for-debug-css)
  - [3.3. references](#33-references)
- [4. install](#4-install)

# 1. run on local

## 1.1. prepare environment

```shell
pyenv local 3.9.0
venv_create

make local-setup-development-environment
# ./scripts/bootstrap-dev-debian.sh
make local-run
# make local-run-logging-DEBUG
```

## 1.2. debug

1. run guake with debugpy

```shell
make local-debug
```

2. run debug mode vscode
3. set breakpoints
4. reduce guake windows size, because when debug, guake terminal will stay in screen
5. do something in guake terminale

# 2. How to use "mapping path then opening in vscode feature"

1. Create configs file [.guake.json](.guake.json) in the root folder


2. cd to guake repo

```shell
cd /home/xuananh/repo/guake/
git checkout xuananh
```

3. copy bellow log and paste to terminal

```shell
Traceback (most recent call last):
  File "/app/main.py", line 190, in on_task_received
    strategy = strategies[type_]
```

4. Ctrl + click to "app/main.py", it will open [guake/main.py](guake/main.py) on vscode based on setting in file [.guake.json](.guake.json)

# 3. change stk css style

## 3.1. css file localtion

~/.config/gtk-3.0/gtk.css

## 3.2. using GTK Inspector for debug css

Run guake by command:

```shell
GTK_DEBUG=interactive make local-run
```

it will run guake and GTK Inspector :

![](README.images/gtk-inspector-1.png)


do as above image to inspect element in guake, it will show as below

![](README.images/gtk-inspector-2.png)

choose another function: CSS nodes as bellow

![](README.images/gtk-inspector-3.png)

you can see above image to know how to get right css selector and set attribute for it

in above image, we got css selector for selected tab in guake terminal, then set its box-shadow color to highlight selected tab

you can test your css by switch to css tab

![](README.images/gtk-inspector-4.png)

## 3.3. references

https://blog.gtk.org/2017/04/05/the-gtk-inspector/

https://gtkthemingguide.vercel.app/#/creating_gtk_themes?id=selectors

# 4. install

https://guake.readthedocs.io/en/latest/contributing/dev_env.html#install-on-system

`make && sudo make install`

or reinstall

`make reinstall`
