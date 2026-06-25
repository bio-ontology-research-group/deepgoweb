package deepgo.jena;

import org.apache.jena.sparql.pfunction.PropertyFunction;
import org.apache.jena.sparql.pfunction.PropertyFunctionFactory;

public class ComponentsPropertyFunctionFactory implements PropertyFunctionFactory {

    public ComponentsPropertyFunctionFactory() {
    }

    public PropertyFunction create(String uri) {
        return new components();
    }
}
