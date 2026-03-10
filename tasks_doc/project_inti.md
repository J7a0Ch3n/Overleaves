## 需求背景

Overleaves是一款跨平台论文写作agent工具，仿照olcli拉取overleaf项目的内容，通过agent功能协助用户进行论文写作、内容修改、格式调整等操作，最终将修改结果推送回overleaf项目。
我现在要开发这一款工具。

## 需求描述

首先我需要实现论文内容拉取功能，以及相关的GUI设计

## 实现策略/步骤

1. 仿照项目https://github.com/aloth/olcli，用python对overleaf项目使用基于cookie的方式进行拉取到本地软件进行罗列。具体的，要拉取overleaf项目整个项目的文件，然后，调用overleaf的编译器进行远程编译，编译成功后同样把pdf拉取到本地
2. 本地GUI设计，先设计三个子栏，就像overleaf网站一样，最左侧栏能够显示项目文件结构，中间栏显示左侧点击的tex文件内容，最右侧栏显示编译好的pdf。
3. GUI中除了3个显示栏，主要菜单功能现在需要包括：“拉取远程项目”，“远程编译并拉取pdf显示”。
4. 用户在设置里面能配置overleaf cookie，LLM agent等，后续会持续添加。

代码主要使用python开发，GUI使用Flet，方便我后续进行跨平台开发。顺便帮我进行本地环境的配置，我已经安装了python，但是其他依赖也请一起安装。
目前主要在windows上进行开发和测试，在README中写一下具体的编译得到exe的步骤。

## 涉及代码

任意


## 相关知识

无

## 其他


实现后，将代码修改分解成可读的commit写在tasks.md中，并且用git提交commit

