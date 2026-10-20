<!--
 * @Author: Lyq 
 * @Date: 2024-02-29 21:50:44
 * @LastEditors: Lyq 
 * @LastEditTime: 2024-02-29 21:51:00
-->
在 Nest.js 中，controller.ts 文件和 service.ts 文件各自有不同的作用：
Controller 文件（controller.ts）： Controller 文件用于处理应用程序的 HTTP 请求和响应。每个 Controller 类负责处理一个特定的路由或一组相关的路由。在 Controller 类中，您可以定义各种 HTTP 请求方法（如 GET、POST、PUT、DELETE 等）的处理逻辑，包括数据验证、数据处理、调用 Service 层等操作。Controller 类中的方法通常被装饰器（如 @Get、@Post 等）修饰，以将其与特定的路由路径关联起来。

Service 文件（service.ts）： Service 文件用于定义应用程序的业务逻辑。Service 类包含了各种方法来执行数据操作、调用外部服务、执行复杂的业务逻辑等。Service 类的主要作用是封装数据操作和业务逻辑，使 Controller 类保持简单并且专注于处理 HTTP 请求和响应。在 Controller 类中，您可以通过依赖注入的方式将 Service 类注入进来，并在需要的地方调用 Service 类的方法来执行相应的业务逻辑。

通常，Controller 文件中的方法会调用 Service 文件中的方法来执行具体的业务逻辑。这种方式使代码更易于维护和测试，因为业务逻辑被封装在 Service 层中，而 Controller 层则专注于处理 HTTP 请求和响应。