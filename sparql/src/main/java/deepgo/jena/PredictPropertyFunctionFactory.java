package deepgo.jena;

import org.apache.jena.sparql.pfunction.PropertyFunction;
import org.apache.jena.sparql.pfunction.PropertyFunctionFactory;

public class PredictPropertyFunctionFactory implements PropertyFunctionFactory {

    public PredictPropertyFunctionFactory() {
    }

    public PropertyFunction create(String uri) {
        return new predict();
    }
}
