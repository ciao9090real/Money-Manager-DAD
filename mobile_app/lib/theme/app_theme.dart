import 'package:flutter/material.dart';

class AppColors {
  static const background = Color(0xFFF6F4EF);
  static const surface = Color(0xFFFFFFFF);
  static const ink = Color(0xFF182023);
  static const muted = Color(0xFF667073);
  static const border = Color(0xFFE9E7E1);
  static const primary = Color(0xFF365D72);
  static const primarySoft = Color(0xFFEDF2F3);
  static const blue = Color(0xFF55758A);
  static const blueSoft = Color(0xFFEEF2F3);
  static const positive = Color(0xFF2F7D62);
  static const negative = Color(0xFFBF4F31);
  static const warning = Color(0xFF9C6D32);
}

class AppTheme {
  static ThemeData get light {
    final scheme = ColorScheme.fromSeed(
      seedColor: AppColors.primary,
      brightness: Brightness.light,
      surface: AppColors.surface,
      error: AppColors.negative,
    );
    return ThemeData(
      useMaterial3: true,
      fontFamily: 'Inter',
      colorScheme: scheme,
      scaffoldBackgroundColor: AppColors.background,
      textTheme: const TextTheme(
        displaySmall: TextStyle(
          fontFamily: 'SpaceGrotesk',
          color: AppColors.ink,
          fontSize: 36,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.8,
        ),
        headlineSmall: TextStyle(
          color: AppColors.ink,
          fontSize: 27,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.5,
        ),
        titleLarge: TextStyle(
          color: AppColors.ink,
          fontSize: 20,
          fontWeight: FontWeight.w600,
          letterSpacing: 0,
        ),
        titleMedium: TextStyle(
          color: AppColors.ink,
          fontSize: 16,
          fontWeight: FontWeight.w600,
          letterSpacing: 0,
        ),
        bodyLarge: TextStyle(
          color: AppColors.ink,
          fontSize: 16,
          letterSpacing: 0,
        ),
        bodyMedium: TextStyle(
          color: AppColors.ink,
          fontSize: 14,
          letterSpacing: 0,
        ),
        bodySmall: TextStyle(
          color: AppColors.muted,
          fontSize: 12,
          letterSpacing: 0,
        ),
        labelLarge: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          letterSpacing: 0,
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.background,
        foregroundColor: AppColors.ink,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        color: AppColors.surface,
        surfaceTintColor: Colors.transparent,
        elevation: 1.5,
        shadowColor: const Color(0x18000000),
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide.none,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surface,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 14,
          vertical: 14,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AppColors.primary, width: 1.5),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          minimumSize: const Size(48, 48),
          padding: const EdgeInsets.symmetric(horizontal: 18),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.ink,
          minimumSize: const Size(48, 48),
          side: const BorderSide(color: AppColors.border),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        elevation: 2,
        shape: CircleBorder(),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          visualDensity: VisualDensity.compact,
          shape: WidgetStatePropertyAll(
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
          side: const WidgetStatePropertyAll(
            BorderSide(color: AppColors.border),
          ),
          backgroundColor: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.selected)
                ? AppColors.primarySoft
                : AppColors.surface,
          ),
          foregroundColor: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.selected)
                ? AppColors.primary
                : AppColors.muted,
          ),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.primarySoft,
        side: BorderSide.none,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
        labelStyle: const TextStyle(
          color: AppColors.ink,
          fontWeight: FontWeight.w600,
        ),
        iconTheme: const IconThemeData(color: AppColors.primary),
      ),
      navigationBarTheme: const NavigationBarThemeData(
        backgroundColor: AppColors.surface,
        surfaceTintColor: Colors.transparent,
        indicatorColor: AppColors.primarySoft,
        height: 70,
        labelTextStyle: WidgetStatePropertyAll(
          TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            letterSpacing: 0,
          ),
        ),
      ),
      dividerColor: AppColors.border,
    );
  }
}
