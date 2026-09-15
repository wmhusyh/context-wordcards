package com.gongdi.wordcards;

import org.json.JSONArray;
import org.json.JSONObject;
import java.util.LinkedHashMap;
import java.util.Locale;

/** Parses pasted lines or CSV text before anything is written to the database. */
public final class ImportParser {
    public static JSONObject parse(String text, boolean csv) throws Exception {
        LinkedHashMap<String, JSONObject> unique = new LinkedHashMap<>();
        JSONArray errors = new JSONArray();
        JSONArray duplicates = new JSONArray();
        String normalized = text == null ? "" : text.replace("\r\n", "\n").replace('\r', '\n');
        String[] lines = normalized.split("\n", -1);
        for (int index = 0; index < lines.length; index++) {
            String raw = lines[index].trim();
            if (raw.isEmpty()) continue;
            if (csv && index == 0 && raw.replace("\"", "").split(",", 2)[0].trim().matches("(?i)word|单词")) continue;
            String[] parts;
            try { parts = csv ? csvRow(raw) : textRow(raw); }
            catch (Exception e) { errors.put(issue(index + 1, raw, e.getMessage())); continue; }
            String word;
            try { word = Review.normalize(parts[0]); }
            catch (Exception e) { errors.put(issue(index + 1, raw, e.getMessage())); continue; }
            String meaning = parts.length > 1 ? parts[1].trim() : "";
            if (meaning.length() > 500) { errors.put(issue(index + 1, raw, "释义不能超过 500 个字符。")); continue; }
            if (unique.containsKey(word)) {
                duplicates.put(new JSONObject().put("line", index + 1).put("word", word).put("kind", "本批重复"));
                if (unique.get(word).optString("meaning").isEmpty() && !meaning.isEmpty()) unique.get(word).put("meaning", meaning);
                continue;
            }
            unique.put(word, new JSONObject().put("word", word).put("meaning", meaning).put("line", index + 1));
        }
        JSONArray items = new JSONArray();
        for (JSONObject item : unique.values()) items.put(item);
        return new JSONObject().put("items", items).put("errors", errors).put("duplicates", duplicates)
            .put("empty_lines", Math.max(0, lines.length - items.length() - errors.length() - duplicates.length()));
    }

    private static JSONObject issue(int line, String raw, String message) throws Exception {
        return new JSONObject().put("line", line).put("raw", raw).put("message", message);
    }

    private static String[] textRow(String line) {
        String[] candidates = {"\t", "：", ":", " - ", " — ", "＝", "="};
        for (String separator : candidates) {
            int at = line.indexOf(separator);
            if (at > 0) return new String[]{line.substring(0, at).trim(), line.substring(at + separator.length()).trim()};
        }
        String[] spaced = line.split("\\s{2,}", 2);
        return spaced.length == 2 ? spaced : new String[]{line};
    }

    private static String[] csvRow(String line) throws Exception {
        java.util.ArrayList<String> fields = new java.util.ArrayList<>();
        StringBuilder value = new StringBuilder(); boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char ch = line.charAt(i);
            if (ch == '"') {
                if (quoted && i + 1 < line.length() && line.charAt(i + 1) == '"') { value.append('"'); i++; }
                else quoted = !quoted;
            } else if (ch == ',' && !quoted) { fields.add(value.toString()); value.setLength(0); }
            else value.append(ch);
        }
        if (quoted) throw new Exception("CSV 引号没有闭合。");
        fields.add(value.toString());
        if (fields.isEmpty() || fields.get(0).trim().isEmpty()) throw new Exception("缺少单词列。");
        String first = fields.get(0).trim().toLowerCase(Locale.ROOT);
        return new String[]{fields.get(0), fields.size() > 1 ? fields.get(1) : ""};
    }
}
