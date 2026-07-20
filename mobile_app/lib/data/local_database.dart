import 'dart:convert';

import 'package:path/path.dart' as path;
import 'package:sqflite/sqflite.dart';

import '../models/finance_models.dart';

class LocalDatabase {
  Database? _database;

  Future<void> initialize() async {
    if (_database != null) return;
    final root = await getDatabasesPath();
    _database = await openDatabase(
      path.join(root, 'money_manager_mobile.db'),
      version: 1,
      onConfigure: (db) async {
        await db.rawQuery('PRAGMA journal_mode = WAL');
        await db.execute('PRAGMA foreign_keys = ON');
      },
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE records (
            entity_type TEXT NOT NULL,
            id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            deleted_at TEXT,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (entity_type, id)
          )
        ''');
        await db.execute('''
          CREATE TABLE pending_commands (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
              CHECK (status IN ('pending', 'failed')),
            error_message TEXT,
            created_at TEXT NOT NULL
          )
        ''');
        await db.execute('''
          CREATE TABLE sync_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
          ) WITHOUT ROWID
        ''');
        await db.execute(
          'CREATE INDEX idx_records_entity_active '
          'ON records(entity_type, deleted_at)',
        );
        await db.execute(
          'CREATE INDEX idx_pending_status_created '
          'ON pending_commands(status, created_at)',
        );
      },
    );
  }

  Database get _db {
    final value = _database;
    if (value == null) throw StateError('Local database is not initialized');
    return value;
  }

  Future<List<StoredRecord>> records(String entity) async {
    final rows = await _db.query(
      'records',
      where: 'entity_type = ? AND deleted_at IS NULL',
      whereArgs: [entity],
    );
    return rows
        .map(
          (row) => StoredRecord(
            entity: '${row['entity_type']}',
            id: '${row['id']}',
            revision: row['revision'] as int,
            payload:
                jsonDecode('${row['payload_json']}') as Map<String, dynamic>,
          ),
        )
        .toList(growable: false);
  }

  Future<List<PendingCommand>> pendingCommands({
    bool includeFailed = true,
  }) async {
    final rows = await _db.query(
      'pending_commands',
      where: includeFailed ? null : "status = 'pending'",
      orderBy: 'created_at',
    );
    return rows.map(PendingCommand.fromRow).toList(growable: false);
  }

  Future<void> queueCommand(PendingCommand command) async {
    await _db.insert('pending_commands', {
      'id': command.id,
      'type': command.type,
      'payload_json': jsonEncode(command.payload),
      'status': 'pending',
      'created_at': DateTime.now().toUtc().toIso8601String(),
    });
  }

  Future<void> dismissCommand(String commandId) async {
    await _db.delete(
      'pending_commands',
      where: 'id = ?',
      whereArgs: [commandId],
    );
  }

  Future<int> cursor() async {
    final rows = await _db.query(
      'sync_state',
      columns: ['value'],
      where: 'key = ?',
      whereArgs: ['cursor'],
      limit: 1,
    );
    return rows.isEmpty ? 0 : int.tryParse('${rows.first['value']}') ?? 0;
  }

  Future<int> entitySetVersion() async {
    final value = await state('entity_set_version');
    return int.tryParse(value ?? '') ?? 0;
  }

  Future<String?> state(String key) async {
    final rows = await _db.query(
      'sync_state',
      columns: ['value'],
      where: 'key = ?',
      whereArgs: [key],
      limit: 1,
    );
    return rows.isEmpty ? null : '${rows.first['value']}';
  }

  Future<void> applyExchange(Map<String, dynamic> response) async {
    final snapshot = response['snapshot'] == true;
    final changes = (response['changes'] as List<dynamic>? ?? const []);
    final commandResults = (response['commands'] as List<dynamic>? ?? const []);
    final nextCursor = response['cursor'] as int? ?? 0;
    final entitySetVersion = response['entity_set_version'] as int?;

    await _db.transaction((txn) async {
      if (snapshot) await txn.delete('records');
      for (final raw in changes) {
        final change = raw as Map<String, dynamic>;
        final payload = change['payload'] as Map<String, dynamic>;
        final entity = '${change['entity']}';
        final id = '${change['id']}';
        final revision = change['revision'] as int? ?? 1;
        final existing = await txn.query(
          'records',
          columns: ['revision'],
          where: 'entity_type = ? AND id = ?',
          whereArgs: [entity, id],
          limit: 1,
        );
        if (existing.isNotEmpty &&
            (existing.first['revision'] as int) > revision) {
          continue;
        }
        await txn.insert('records', {
          'entity_type': entity,
          'id': id,
          'revision': revision,
          'deleted_at': payload['deleted_at'],
          'payload_json': jsonEncode(payload),
        }, conflictAlgorithm: ConflictAlgorithm.replace);
      }
      for (final raw in commandResults) {
        final result = raw as Map<String, dynamic>;
        final id = '${result['id']}';
        if (result['status'] == 'accepted') {
          await txn.delete(
            'pending_commands',
            where: 'id = ?',
            whereArgs: [id],
          );
        } else {
          await txn.update(
            'pending_commands',
            {
              'status': 'failed',
              'error_message':
                  '${result['error'] ?? 'Desktop rejected this change'}',
            },
            where: 'id = ?',
            whereArgs: [id],
          );
        }
      }
      await txn.insert('sync_state', {
        'key': 'cursor',
        'value': '$nextCursor',
      }, conflictAlgorithm: ConflictAlgorithm.replace);
      if (entitySetVersion != null) {
        await txn.insert('sync_state', {
          'key': 'entity_set_version',
          'value': '$entitySetVersion',
        }, conflictAlgorithm: ConflictAlgorithm.replace);
      }
      await txn.insert('sync_state', {
        'key': 'last_sync_at',
        'value': DateTime.now().toUtc().toIso8601String(),
      }, conflictAlgorithm: ConflictAlgorithm.replace);
    });
  }

  Future<void> clearSyncedData() async {
    await _db.transaction((txn) async {
      await txn.delete('records');
      await txn.delete('pending_commands');
      await txn.delete('sync_state');
    });
  }
}
