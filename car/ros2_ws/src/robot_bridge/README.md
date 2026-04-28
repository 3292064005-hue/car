# robot_bridge

## 职责
- Ubuntu 运行时与外部板级 runtime 之间的桥接 transport / protocol / projection

## 输入 / 输出
- transport payload、summary、故障与 telemetry 映射

## 扩展点
- protocol policy、transport runtime、projection layer

## 禁改区
- 不要越过仓外边界声明实机执行闭环

## 测试入口
- protocol / replay policy / report surface 相关 pytest
