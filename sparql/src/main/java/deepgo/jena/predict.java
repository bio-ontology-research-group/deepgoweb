package deepgo.jena;

import org.apache.jena.graph.Node;
import org.apache.jena.sparql.expr.NodeValue;
import org.apache.jena.atlas.iterator.Iter;
import org.apache.jena.graph.NodeFactory;
import org.apache.jena.query.QueryBuildException;
import org.apache.jena.sparql.core.Var;
import org.apache.jena.sparql.engine.ExecutionContext;
import org.apache.jena.sparql.engine.QueryIterator;
import org.apache.jena.sparql.engine.binding.Binding;
import org.apache.jena.sparql.engine.binding.BindingMap;
import org.apache.jena.sparql.engine.binding.BindingFactory;
import org.apache.jena.sparql.engine.iterator.QueryIterPlainWrapper;
import org.apache.jena.sparql.pfunction.PFuncListAndList;
import org.apache.jena.sparql.pfunction.PropFuncArg;
import org.apache.jena.sparql.util.IterLib;
import java.util.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import deepgo.Functions;

/**
 * Predictor-aware integrated prediction. Backwards-compatible *addition* — the
 * legacy {@code dg:deepgo} property function is unchanged.
 *
 *   (?subontology ?go ?label ?score) dg:predict (?sequence ?threshold ?predictor)
 *
 * The predictor argument is optional; it defaults to "deepgoplus" so a 2-arg
 * object list behaves like dg:deepgo.
 */
public class predict extends PFuncListAndList {

    Logger logger;

    public predict() {
        super();
        logger = LoggerFactory.getLogger(predict.class);
    }

    @Override
    public void build(PropFuncArg argSubject, Node predicate,
                      PropFuncArg argObject, ExecutionContext execCxt) {
        super.build(argSubject, predicate, argObject, execCxt);
        if (argSubject.getArgListSize() != 4)
            throw new QueryBuildException(
                "Subject list must contain exactly 4 variables: " +
                "GO subontology, GO IRI, label, score");
        int n = argObject.getArgListSize();
        if (n != 2 && n != 3)
            throw new QueryBuildException(
                "Object list must contain 2 or 3 arguments: " +
                "sequence, threshold[, predictor]");
    }

    @Override
    public QueryIterator execEvaluated(final Binding binding,
                                       final PropFuncArg subject,
                                       final Node predicate,
                                       final PropFuncArg object,
                                       final ExecutionContext execCxt) {
        String sequence = object.getArg(0).toString().replace("\"", "");
        double threshold = Double.parseDouble(
            object.getArg(1).getLiteralLexicalForm().toString());
        String predictor = "deepgoplus";
        if (object.getArgListSize() == 3) {
            predictor = object.getArg(2).getLiteralLexicalForm().toString();
        }
        ArrayList<String[]> arr = Functions.predict("latest", sequence, threshold, predictor);
        if (arr.size() == 0) {
            return IterLib.noResults(execCxt);
        }
        ArrayList<Node[]> result = new ArrayList<Node[]>();
        for (int i = 0; i < arr.size(); i++) {
            result.add(new Node[]{
                    NodeValue.makeNodeString(arr.get(i)[0]).asNode(),
                    NodeFactory.createURI(arr.get(i)[1]),
                    NodeValue.makeNodeString(arr.get(i)[2]).asNode(),
                    NodeValue.makeNodeDouble(Double.parseDouble(arr.get(i)[3])).asNode(),
                });
        }
        Node subOnt = subject.getArg(0);
        Node node = subject.getArg(1);
        Node label = subject.getArg(2);
        Node score = subject.getArg(3);

        if (Var.isVar(subOnt) && Var.isVar(node) && Var.isVar(label) && Var.isVar(score)) {
            final Var subVar = Var.alloc(subOnt);
            final Var nodeVar = Var.alloc(node);
            final Var labelVar = Var.alloc(label);
            final Var scoreVar = Var.alloc(score);

            Iterator<Binding> it = Iter.map(
                    result.iterator(),
                    item -> {
                        BindingMap b = BindingFactory.create(binding);
                        b.add(subVar, item[0]);
                        b.add(nodeVar, item[1]);
                        b.add(labelVar, item[2]);
                        b.add(scoreVar, item[3]);
                        return b;
                    });
            return new QueryIterPlainWrapper(it, execCxt);
        }
        return IterLib.noResults(execCxt);
    }
}
