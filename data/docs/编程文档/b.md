虚拟dome

虚拟dome本质上是一个javascripct 对象 当数据驱动的时候 不是直接操作dom 而是先更新虚拟dome
通过diff算法 找出最小变更集 然后批量更新真实dom

diff算法 UI不需要跨级比较 不同类型元素产生不同的书 开发者可以通过可以提示那些子元素可以销毁
减少不必要的 DOM 创建和销毁
准确识别新增、删除、移动
保持组件内部状态，比如输入框内容、展开状态
fiber

react 16是通过递归来计算 16之后每个节点都是挂载一个小任务 支持并发任务 支持优先级调度

虚拟dome 和 fiber 区别

react 虚拟dome本质上是一个javascripct 对象 react不会操作真是dome 当数据驱动的时候 先更新虚拟dome
通过diff算法来找出最小变更 减少真实dome带来的性能损耗

useState  可控组件 非可控 调用是同步的 但是每次生成的值 新值等下一次渲染才是最新的 循环里面不可调用因为 React 内部通过 Hooks 调用顺序 来匹配每个 useState 对应的状态如果顺序变化，React 就无法正确找到上一次存储的状态，会出现状态错乱。React 会对状态更新做 批处理，在一次事件处理结束后统一更新 UI，从而减少不必要的重渲染
 
useRef     非可控 跨渲染持久化 修改 .current 不会触发重新渲染 可存任意值
useEffect  只在挂载时执行一次，卸载时执行清理 当 a 或 b 变化时重新执行
useCallback 缓存函数引用 缓存函数引用，适合传给子组件或作为 useEffect 依赖
useMemo 缓存计算结果
useImperativeHandle
forwardRef
![alt text](image.png)