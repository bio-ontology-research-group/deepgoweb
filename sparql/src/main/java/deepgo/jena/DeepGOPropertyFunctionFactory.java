package deepgo.jena;

import org.apache.jena.sparql.pfunction.PropertyFunction;
import org.apache.jena.sparql.pfunction.PropertyFunctionFactory;
import java.util.Map;

public class DeepGOPropertyFunctionFactory implements PropertyFunctionFactory {

    public DeepGOPropertyFunctionFactory() {
    }

    public PropertyFunction create(String uri) {
	return new deepGO();
    }
}
