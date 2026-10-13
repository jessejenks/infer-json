/**
 * @name Unescaped input in generated code
 * @kind path-problem
 * @problem.severity error
 * @id infer-json/unescaped-output
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking
import semmle.python.ApiGraphs

predicate inFile(DataFlow::Node node, string fileName) {
  node.getLocation().getFile().getShortName() = fileName
}

predicate inEmitter(DataFlow::Node node) { inFile(node, ["emit_ts.py", "emit_py.py", "emit_go.py"]) }

predicate isCallTo(DataFlow::Node node, string functionName) {
  node.(DataFlow::CallCfgNode).getFunction().asExpr().(Name).getId() = functionName
}

predicate passesCheck(DataFlow::GuardNode check, ControlFlowNode value, boolean outcome) {
  outcome = true and
  exists(CallNode call | call = check |
    call.getFunction().(NameNode).getId() = "_is_valid_go_tag_name" and value = call.getArg(0)
    or
    call.getFunction().(AttrNode).getObject("isidentifier") = value
  )
}

module UnescapedOutputConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    inEmitter(source) and
    (
      // `key` in `for key, (...) in fields`
      source.asExpr() = any(For loop).getTarget().(Tuple).getElt(0)
      or
      // `t.value` of a string literal type
      source.(DataFlow::AttrRead).getAttributeName() = "value"
    )
  }

  predicate isSink(DataFlow::Node sink) {
    inEmitter(sink) and
    exists(Fstring f |
      sink.asExpr() = f.getAValue() and
      not exists(Raise r | r.contains(f))
    )
  }

  predicate isBarrier(DataFlow::Node node) {
    inFile(node, ["emit_ts.py", "emit_py.py"]) and node = API::moduleImport("json").getMember("dumps").getACall()
    or
    inFile(node, "emit_go.py") and isCallTo(node, "normalize_to_pascal")
    or
    node = DataFlow::BarrierGuard<passesCheck/3>::getABarrierNode()
  }
}

module UnescapedOutputFlow = TaintTracking::Global<UnescapedOutputConfig>;

import UnescapedOutputFlow::PathGraph

from UnescapedOutputFlow::PathNode source, UnescapedOutputFlow::PathNode sink
where UnescapedOutputFlow::flowPath(source, sink)
select sink.getNode(), source, sink, "$@ reaches generated code without escaping.", source.getNode(),
  "Input text"
