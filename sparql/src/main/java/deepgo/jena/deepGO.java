package deepgo.jena;

import org.apache.jena.graph.Node;
import org.apache.jena.sparql.expr.NodeValue;
import org.apache.jena.sparql.expr.ExprEvalException;
import org.apache.jena.sparql.util.FmtUtils;

import org.apache.jena.atlas.iterator.Iter ;
import org.apache.jena.atlas.lib.StrUtils ;
import org.apache.jena.graph.Node ;
import org.apache.jena.graph.NodeFactory ;
import org.apache.jena.query.QueryBuildException;
import org.apache.jena.rdf.model.impl.Util ;
import org.apache.jena.sparql.core.Var ;
import org.apache.jena.sparql.engine.ExecutionContext ;
import org.apache.jena.sparql.engine.QueryIterator ;
import org.apache.jena.sparql.engine.binding.Binding ;
import org.apache.jena.sparql.engine.binding.BindingMap ;
import org.apache.jena.sparql.engine.binding.BindingFactory ;
import org.apache.jena.sparql.engine.iterator.QueryIterPlainWrapper ;
import org.apache.jena.sparql.pfunction.PFuncListAndList ;
import org.apache.jena.sparql.pfunction.PropFuncArg ;
import org.apache.jena.sparql.util.IterLib;
import java.io.*;
import java.util.*;
import org.json.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.apache.jena.ext.xerces.util.URI;


import org.apache.http.*;
import org.apache.http.client.methods.*;
import org.apache.http.util.*;
import org.apache.http.entity.*;
import org.apache.http.impl.client.*;

import deepgo.Functions;

public class deepGO extends PFuncListAndList {

    Logger logger;
    
    public deepGO() {
	super();
	logger = LoggerFactory.getLogger(deepGO.class);
    }

    @Override
    public void build(PropFuncArg argSubject, Node predicate,
		      PropFuncArg argObject, ExecutionContext execCxt) {
        super.build(argSubject, predicate, argObject, execCxt);
	if (argSubject.getArgListSize() != 4)
            throw new QueryBuildException(
		"Subject list must contain exactly 3 variables, " +
		"GO subontology, GO IRI, label, score");
	
	if (argObject.getArgListSize() != 2)
            throw new QueryBuildException(
		"Object list must contain exactly two arguments, " +
		"sequence and threshold");
	        
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
	ArrayList<String[]> arr = Functions.deepgo(sequence, threshold);
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

        // Any other case: Return nothing
        return IterLib.noResults(execCxt);
    }

}
