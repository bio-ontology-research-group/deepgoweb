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
    
    public static final String DEEPGO_API_URI = "http://localhost/deepgo/api/create/";
    public static final String NAMESPACE = "http://deepgoplus.bio2vec.net/";
    
    public static ArrayList<String[]> deepgo(String sequence, double threshold) {
        return deepgo("latest", sequence, threshold);
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
                    result.add(new String[]{
                            obj.get("name").toString(),
                            goArr.get(0).toString(),
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
