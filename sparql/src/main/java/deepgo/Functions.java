package deepgo;

import java.io.*;
import java.util.*;
import org.json.*;

import org.apache.http.*;
import org.apache.http.client.methods.*;
import org.apache.http.util.*;
import org.apache.http.entity.*;
import org.apache.http.impl.client.*;


public class Functions {
    
    // Base URL of the Django app the property functions call back into. Defaults to
    // http://localhost (nginx-fronted prod); override for other deployments via the
    // DEEPGO_API_BASE env var or -Ddeepgo.api.base=... system property.
    private static String apiBase() {
        String b = System.getenv("DEEPGO_API_BASE");
        if (b == null || b.isEmpty())
            b = System.getProperty("deepgo.api.base", "http://localhost");
        return b.replaceAll("/+$", "");
    }
    public static final String DEEPGO_API_URI = apiBase() + "/deepgo/api/create";
    // Predictor-aware endpoint (backwards-compatible addition; see deepgo.rest_views).
    public static final String DEEPGO_PREDICT_URI = apiBase() + "/deepgo/api/predict";
    public static final String NAMESPACE = "http://deepgoplus.bio2vec.net/";

    public static ArrayList<String[]> deepgo(String sequence, double threshold) {
        return deepgo("latest", sequence, threshold);
    }

    /**
     * Predictor-aware integrated prediction. Same (subontology, GO IRI, label,
     * score) rows as {@link #deepgo}, but routed through the new api/predict
     * endpoint with an explicit predictor (e.g. "dgpp-light", "deepgoplus").
     */
    public static ArrayList<String[]> predict(String version, String sequence,
                                              double threshold, String predictor) {
        ArrayList<String[]> result = new ArrayList<String[]>();
        String query = new JSONObject()
            .put("version", version)
            .put("predictor", predictor)
            .put("data_format", "enter")
            .put("data", sequence)
            .put("threshold", threshold)
            .toString();
        JSONObject root = queryAPI(DEEPGO_PREDICT_URI, query);
        if (root == null) {
            return result;
        }
        JSONArray arr = (JSONArray)(root.get("predictions"));
        for (int i = 0; i < arr.length(); i++) {
            JSONObject pred = (JSONObject)arr.get(i);
            JSONArray funcs = (JSONArray)(pred.get("functions"));
            for (int j = 0; j < funcs.length(); j++) {
                JSONObject aspect = (JSONObject) funcs.get(j);
                JSONArray subFuncs = (JSONArray)(aspect.get("functions"));
                for (int k = 0; k < subFuncs.length(); k++) {
                    JSONArray goArr = (JSONArray) subFuncs.get(k);
                    String goURI = goArr.get(0).toString().replace(
                        "GO:", "http://purl.obolibrary.org/obo/GO_");
                    result.add(new String[]{
                            aspect.get("name").toString(),
                            goURI,
                            goArr.get(1).toString(),
                            goArr.get(2).toString()
                        });
                }
            }
        }
        return result;
    }

    /**
     * Per-component substreams for predictor (e.g. "dgpp-light"): one row per
     * (component label, GO IRI, label, score) — ProteInfer, STRING-Net, the
     * hierarchy-aware CNN, ESM2-kNN, DIAMOND, ... Empty for predictors that do
     * not expose components.
     */
    public static ArrayList<String[]> components(String version, String sequence,
                                                 double threshold, String predictor) {
        ArrayList<String[]> result = new ArrayList<String[]>();
        String query = new JSONObject()
            .put("version", version)
            .put("predictor", predictor)
            .put("data_format", "enter")
            .put("data", sequence)
            .put("threshold", threshold)
            .toString();
        JSONObject root = queryAPI(DEEPGO_PREDICT_URI, query);
        if (root == null) {
            return result;
        }
        JSONArray comps = root.optJSONArray("components");
        if (comps == null) {
            return result;
        }
        // components: per-protein {component_label: [[go, name, score], ...]}.
        for (int i = 0; i < comps.length(); i++) {
            JSONObject perProt = comps.optJSONObject(i);
            if (perProt == null) {
                continue;
            }
            for (String label : perProt.keySet()) {
                JSONArray terms = perProt.getJSONArray(label);
                for (int k = 0; k < terms.length(); k++) {
                    JSONArray goArr = (JSONArray) terms.get(k);
                    String goURI = goArr.get(0).toString().replace(
                        "GO:", "http://purl.obolibrary.org/obo/GO_");
                    result.add(new String[]{
                            label,
                            goURI,
                            goArr.get(1).toString(),
                            goArr.get(2).toString()
                        });
                }
            }
        }
        return result;
    }
    
    public static ArrayList<String[]> deepgo(String version, String sequence, double threshold) {
	ArrayList<String[]> result = new ArrayList<String[]>();
	String query = new JSONObject()
            .put("version", version)
	    .put("data_format", "enter")
	    .put("data", sequence)
	    .put("threshold", threshold)
	    .toString();
	
	JSONObject obj = queryAPI(query);	
	if (obj == null) {
	    return result;
	}
	JSONArray arr = (JSONArray)(obj.get("predictions"));
	for (int i = 0; i < arr.length(); i++) {
	    obj = (JSONObject)arr.get(i);
            JSONArray funcs = (JSONArray)(obj.get("functions"));
            for (int j = 0; j < funcs.length(); j++) {
                obj = (JSONObject) funcs.get(j);
                JSONArray subFuncs = (JSONArray)(obj.get("functions"));
                for (int k = 0; k < subFuncs.length(); k++) {
                    JSONArray goArr = (JSONArray) subFuncs.get(k);
                    String goURI = goArr.get(0).toString().replace("GO:", "http://purl.obolibrary.org/obo/GO_");
                    result.add(new String[]{
                            obj.get("name").toString(),
                            goURI,
                            goArr.get(1).toString(),
                            goArr.get(2).toString()
                        });
                }
            }
	}
        
	return result;
    }

    public static JSONObject queryAPI(String query) {
	return queryAPI(DEEPGO_API_URI, query);
    }

    public static JSONObject queryAPI(String uri, String query) {
	CloseableHttpClient client = HttpClients.createDefault();
	JSONObject result = null;
	try {
	    try {
		HttpPost post = new HttpPost(uri);
		StringEntity requestEntity = new StringEntity(query,
							      ContentType.APPLICATION_JSON);
		post.setEntity(requestEntity);
		CloseableHttpResponse response = client.execute(post);
		try {
		    // Execute the method.
		    int statusCode = response.getStatusLine().getStatusCode();
		    HttpEntity entity = response.getEntity();
			
		    if (statusCode < 200 || statusCode >= 300) {
			System.err.println("Method failed: " + response.getStatusLine());
                        String responseBody = EntityUtils.toString(entity, "UTF-8");
			System.err.println(responseBody);
		    } else {
			// Read the response body.
			String responseBody = EntityUtils.toString(entity, "UTF-8");
			// Deal with the response.
			// Use caution: ensure correct character encoding and is not binary data
			result = new JSONObject(responseBody);
		    }
		    EntityUtils.consume(entity);
		} finally {
		    // Release the connection.
		    response.close();
		}
	    } finally {
		client.close();
	    }
	} catch (IOException ex) {
	    ex.printStackTrace();
	}
	return result;
    }
}
