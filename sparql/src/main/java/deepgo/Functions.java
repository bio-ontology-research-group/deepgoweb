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
    
    public static final String DEEPGO_API_URI = "http://localhost/deepgo/api/create";
    public static final String NAMESPACE = "http://deepgoplus.bio2vec.net/";
    
    public static ArrayList<String[]> deepgo(String sequence, double threshold) {
        return deepgo("latest", sequence, threshold, null);
    }

    public static ArrayList<String[]> deepgo(String version, String sequence, double threshold) {
        return deepgo(version, sequence, threshold, null);
    }

    // model selects the predictor exposed by the REST API: null/"" -> server default
    // (deepgoplus); "dgpp-light" -> DeepGO-PlusPlus-Light; "dgpp-light-mcm" -> the
    // hierarchy-aware (C-HMCNN) CPU variant. Sent as the API's "model_name" field.
    public static ArrayList<String[]> deepgo(String version, String sequence,
                                             double threshold, String model) {
	ArrayList<String[]> result = new ArrayList<String[]>();
	JSONObject queryObj = new JSONObject()
            .put("version", version)
	    .put("data_format", "enter")
	    .put("data", sequence)
	    .put("threshold", threshold);
	if (model != null && !model.isEmpty()) {
	    queryObj.put("model_name", model);
	}
	String query = queryObj.toString();
	
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
	CloseableHttpClient client = HttpClients.createDefault();
	JSONObject result = null;
	try {
	    try {
		HttpPost post = new HttpPost(DEEPGO_API_URI);
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
