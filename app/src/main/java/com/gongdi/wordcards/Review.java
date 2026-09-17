package com.gongdi.wordcards;
import java.time.LocalDate;
public final class Review {
    public static String normalize(String input) {
        String word = input.trim().toLowerCase(java.util.Locale.ROOT).replaceAll("\\s+", " ");
        if (word.length() > 80 || !word.matches("[a-z]+(?:[ '\\-][a-z]+)*")) throw new IllegalArgumentException("请输入英文单词或短语，最多 80 个字符。");
        return word;
    }
    public static String[] next(int stage, int rating, LocalDate today) {
        if (stage < 0 || stage > 7 || rating < 1 || rating > 3) throw new IllegalArgumentException("复习数据无效。");
        int[] intervals={1,2,4,7,15,30,60,120};int days=1;
        if (rating == 1) { days=intervals[stage];stage=Math.min(7,stage+1); }
        else if(rating==2)stage=Math.max(0,stage-1);
        else stage=0;
        return new String[]{Integer.toString(stage), today.plusDays(days).toString()};
    }
}
