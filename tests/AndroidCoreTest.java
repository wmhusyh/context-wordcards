import com.gongdi.wordcards.ApiClient;
import com.gongdi.wordcards.ImportParser;
import com.gongdi.wordcards.Review;
import java.time.LocalDate;
import java.util.Arrays;
import org.json.JSONArray;
import org.json.JSONObject;

public class AndroidCoreTest {
    static int checks;
    static void eq(Object a,Object b){checks++;if(!a.equals(b))throw new AssertionError(a+" != "+b);}
    public static void main(String[] args)throws Exception{
        JSONObject parsed=ImportParser.parse("Passport: 护照\n\npassport\ncheck in\t办理登机\n错误123",false);
        eq(parsed.getJSONArray("items").length(),2);eq(parsed.getJSONArray("duplicates").length(),1);eq(parsed.getJSONArray("errors").length(),1);
        JSONObject csv=ImportParser.parse("word,meaning\n\"boarding pass\",登机牌",true);eq(csv.getJSONArray("items").length(),1);
        eq(ApiClient.endpoint("https://api.example.com/v1/",true),"https://api.example.com/v1/responses");eq(ApiClient.endpoint("https://api.example.com/v1/responses",false),"https://api.example.com/v1/chat/completions");
        boolean failed=false;try{ApiClient.endpoint("http://example.com/v1",false);}catch(Exception e){failed=true;}eq(failed,true);
        eq(Review.normalize(" Boarding   Pass "),"boarding pass");eq(Arrays.toString(Review.next(0,1,LocalDate.of(2026,12,31))),"[1, 2027-01-01]");
        JSONArray words=new JSONArray().put(new JSONObject().put("word","passport").put("meaning","护照"));JSONArray known=new JSONArray().put(new JSONObject().put("word","travel").put("meaning","旅行").put("mastery",2).put("scenes",new JSONArray()));
        JSONObject rp=ApiClient.classificationPayload(words,known,"model",true);eq(rp.getJSONObject("text").getJSONObject("format").getString("type"),"json_schema");eq(rp.getBoolean("store"),false);
        JSONObject cp=ApiClient.classificationPayload(words,known,"model",false);eq(cp.getJSONObject("response_format").getString("type"),"json_schema");
        System.out.println("PASS: "+checks+" Android core checks");
    }
}
