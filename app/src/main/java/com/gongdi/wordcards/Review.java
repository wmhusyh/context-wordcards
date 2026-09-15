package com.gongdi.wordcards;
import java.time.LocalDate;
public final class Review {
    public static String normalize(String input) {
        String word = input.trim().toLowerCase(java.util.Locale.ROOT).replaceAll("\\s+", " ");
        if (word.length() > 80 || !word.matches("[a-z]+(?:[ '\\-][a-z]+)*")) throw new IllegalArgumentException("请输入英文单词或短语，最多 80 个字符。");
        return word;
    }
    public static String[] next(int stage, int rating, LocalDate today) {
        if (stage < 0 || stage > 4 || rating < 1 || rating > 3) throw new IllegalArgumentException("复习数据无效。");
        int days = 1;
        if (rating == 1) { days = new int[]{1,3,7,14,30}[stage]; stage = Math.min(4, stage+1); }
        if (rating == 3) stage = 0;
        return new String[]{Integer.toString(stage), today.plusDays(days).toString()};
    }
}
