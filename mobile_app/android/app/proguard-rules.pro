# SQLCipher is loaded through JNI and reflection. Preserve its native bridge
# when release builds enable code shrinking.
-keep class net.sqlcipher.** { *; }
-keep class net.zetetic.database.sqlcipher.** { *; }
