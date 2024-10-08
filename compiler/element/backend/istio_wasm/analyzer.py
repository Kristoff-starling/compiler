from compiler.element.backend.istio_wasm.wasmgen import WasmContext
from compiler.element.node import *
from compiler.element.visitor import Visitor

FUNC_INIT = "init"
FUNC_REQ_HEADER = "req_hdr"
FUNC_REQ_BODY = "req_body"
FUNC_RESP_HEADER = "resp_hdr"
FUNC_RESP_BODY = "resp_body"


def set_method(name: str, ctx: WasmContext, method: MethodType):
    # If var name is not in the state definition, it's proabably a temporary variable.
    if name not in ctx.state_names:
        return

    if (
        name not in ctx.access_ops[ctx.current_procedure]
        or ctx.access_ops[ctx.current_procedure][name] != MethodType.SET
    ):
        ctx.access_ops[ctx.current_procedure][name] = method


class AccessAnalyzer(
    Visitor
):  # AccessAnalyzer is used to analyze the IR and record the access operations.
    # The operations are then used to avoid unnecessary locks and RPC decode when generating the corresponding WASM code.
    def __init__(self, placement: str):
        self.placement = placement
        if placement not in ["client", "server", "ambient"]:
            raise ValueError(f"invalid placement {placement}")

    def visitNode(self, node: Node, ctx: WasmContext) -> str:
        pass

    def visitProgram(self, node: Program, ctx: WasmContext) -> str:
        node.definition.accept(self, ctx)
        node.init.accept(self, ctx)
        node.req.accept(self, ctx)
        node.resp.accept(self, ctx)

    def visitState(self, node: State, ctx: WasmContext):
        for (var, _, cons, _, _) in node.state:
            ctx.state_names.append(var.name)
            if cons.name == "strong":
                ctx.strong_access_args[var.name] = ""

    def visitProcedure(self, node: Procedure, ctx: WasmContext):
        match node.name:
            case "init":
                ctx.current_procedure = FUNC_INIT
            case "req":
                ctx.current_procedure = FUNC_REQ_BODY
            case "resp":
                ctx.current_procedure = FUNC_RESP_BODY
            case _:
                raise Exception("unknown function")
        for b in node.body:
            b.accept(self, ctx)

    def visitStatement(self, node: Statement, ctx: WasmContext):
        if node.stmt != None:
            node.stmt.accept(self, ctx)

    def visitMatch(self, node: Match, ctx: WasmContext):
        node.expr.accept(self, ctx)
        for p, s in node.actions:
            for st in s:
                st.accept(self, ctx)

    def visitForeach(self, node: Foreach, ctx: WasmContext):
        node.func.accept(self, ctx)

    def visitLambdaFunc(self, node: LambdaFunc, ctx: WasmContext):
        for st in node.body:
            st.accept(self, ctx)

    def visitAssign(self, node: Assign, ctx: WasmContext):
        if isinstance(node.left, Identifier):
            names = [node.left.name]
        elif isinstance(node.left, Pair):
            assert isinstance(node.left.first, Identifier)
            assert isinstance(node.left.second, Identifier)
            names = [node.left.first.name, node.left.second.name]
        for name in names:
            set_method(name, ctx, MethodType.SET)
        node.right.accept(self, ctx)

    def visitPattern(self, node: Pattern, ctx: WasmContext):
        pass

    def visitExpr(self, node: Expr, ctx: WasmContext):
        if isinstance(node.lhs, Identifier):
            set_method(node.lhs.name, ctx, MethodType.GET)
        if isinstance(node.rhs, Identifier):
            set_method(node.rhs.name, ctx, MethodType.GET)

        node.lhs.accept(self, ctx)
        node.rhs.accept(self, ctx)

    def visitIdentifier(self, node: Identifier, ctx: WasmContext):
        pass

    def visitPair(self, node: Pair, ctx: WasmContext):
        pass

    def visitConsistencyDecorator(self, node: ConsistencyDecorator, ctx: WasmContext):
        pass

    def visitCombinerDecorator(self, node: CombinerDecorator, ctx: WasmContext):
        pass

    def visitPersistenceDecorator(self, node: PersistenceDecorator, ctx: WasmContext):
        pass

    def visitType(self, node: Type, ctx: WasmContext):
        pass

    def visitFuncCall(self, node: FuncCall, ctx: WasmContext):
        for arg in node.args:
            if isinstance(arg, Identifier):
                set_method(arg.name, ctx, MethodType.GET)
            arg.accept(self, ctx)

    def visitMethodCall(self, node: MethodCall, ctx: WasmContext):
        # Add access operations to the corresponding function.
        # If there are multiple operations on the same object, the set takes priority.
        set_method(node.obj.name, ctx, node.method)
        if node.obj.name in ctx.strong_access_args and node.method == MethodType.GET:
            assert len(node.args) == 1, "invalid #arg"
            ctx.strong_access_args[node.obj.name] = node.args[0]

        # Handle nested method calls
        for arg in node.args:
            arg.accept(self, ctx)

    def visitSend(self, node: Send, ctx: WasmContext) -> str:
        pass

    def visitLiteral(self, node: Literal, ctx: WasmContext):
        pass

    def visitError(self, node: Error, ctx: WasmContext) -> str:
        pass
