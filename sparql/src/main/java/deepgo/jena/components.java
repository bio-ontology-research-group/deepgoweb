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
import org.apache.jena.sparql.engine.binding.BindingBuilder;
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
 * Per-component substreams of a predictor (e.g. dgpp-light): ProteInfer,
 * STRING-Net, the hierarchy-aware CNN, ESM2-kNN, DIAMOND, ... The first subject
 * variable binds the component label, so a query can filter to one substream.
 *
 *   (?component ?go ?label ?score) dg:components (?sequence ?threshold ?predictor)
 *
 * The predictor argument is optional and defaults to "dgpp-light" (the only
 * predictor that currently exposes components).
 */
public class components extends PFuncListAndList {

    Logger logger;

    public components() {
        super();
        logger = LoggerFactory.getLogger(components.class);
    }

    @Override
    public void build(PropFuncArg argSubject, Node predicate,
                      PropFuncArg argObject, ExecutionContext execCxt) {
        super.build(argSubject, predicate, argObject, execCxt);
        if (argSubject.getArgListSize() != 4)
            throw new QueryBuildException(
                "Subject list must contain exactly 4 variables: " +
                "component, GO IRI, label, score");
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
        String predictor = "dgpp-light";
        if (object.getArgListSize() == 3) {
            predictor = object.getArg(2).getLiteralLexicalForm().toString();
        }
        ArrayList<String[]> arr = Functions.components("latest", sequence, threshold, predictor);
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
        Node comp = subject.getArg(0);
        Node node = subject.getArg(1);
        Node label = subject.getArg(2);
        Node score = subject.getArg(3);

        if (Var.isVar(comp) && Var.isVar(node) && Var.isVar(label) && Var.isVar(score)) {
            final Var compVar = Var.alloc(comp);
            final Var nodeVar = Var.alloc(node);
            final Var labelVar = Var.alloc(label);
            final Var scoreVar = Var.alloc(score);

            Iterator<Binding> it = Iter.map(
                    result.iterator(),
                    item -> {
                        BindingBuilder b = BindingFactory.builder(binding);
                        b.add(compVar, item[0]);
                        b.add(nodeVar, item[1]);
                        b.add(labelVar, item[2]);
                        b.add(scoreVar, item[3]);
                        return b.build();
                    });
            return QueryIterPlainWrapper.create(it, execCxt);
        }
        return IterLib.noResults(execCxt);
    }
}
