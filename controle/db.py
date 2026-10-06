import sqlite3
import os
import pandas as pd

DB_PATH = "database/escola_relacional.db"

def obter_conexao():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    return conn

def inicializar_banco():
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS turmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_turma TEXT UNIQUE NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alunos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_aluno TEXT NOT NULL,
            numero_chamada TEXT,
            turma_id INTEGER,
            FOREIGN KEY (turma_id) REFERENCES turmas (id) ON DELETE CASCADE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS disciplinas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_disciplina TEXT UNIQUE NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo TEXT NOT NULL,
            aluno_id INTEGER,
            disciplina_id INTEGER,
            nota_parcial REAL DEFAULT 0.0,
            nota_diversificada REAL DEFAULT 0.0,
            avaliacao_trimestral REAL DEFAULT 0.0,
            nota_final REAL DEFAULT 0.0,
            FOREIGN KEY (aluno_id) REFERENCES alunos (id) ON DELETE CASCADE,
            FOREIGN KEY (disciplina_id) REFERENCES disciplinas (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

def buscar_periodos():
    conn = obter_conexao()
    df = pd.read_sql_query("SELECT DISTINCT periodo FROM notas ORDER BY periodo", conn)
    conn.close()
    return df

def buscar_turmas():
    conn = obter_conexao()
    df = pd.read_sql_query("SELECT id, nome_turma FROM turmas ORDER BY nome_turma", conn)
    conn.close()
    return df

def buscar_disciplinas():
    conn = obter_conexao()
    df = pd.read_sql_query("SELECT id, nome_disciplina FROM disciplinas ORDER BY nome_disciplina", conn)
    conn.close()
    return df

def buscar_turmas_por_periodo(periodo):
    conn = obter_conexao()
    query = '''
        SELECT DISTINCT t.id, t.nome_turma
        FROM turmas t
        JOIN alunos a ON t.id = a.turma_id
        JOIN notas n ON a.id = n.aluno_id
        WHERE n.periodo = ?
        ORDER BY t.nome_turma
    '''
    df = pd.read_sql_query(query, conn, params=(periodo,))
    conn.close()
    return df

def buscar_alunos_por_turma(periodo, nome_turma):
    conn = obter_conexao()
    query = '''
        SELECT DISTINCT a.id, a.nome_aluno, a.numero_chamada
        FROM alunos a
        JOIN turmas t ON a.turma_id = t.id
        JOIN notas n ON a.id = n.aluno_id
        WHERE n.periodo = ? AND t.nome_turma = ?
        ORDER BY CAST(a.numero_chamada AS INTEGER), a.nome_aluno
    '''
    df = pd.read_sql_query(query, conn, params=(periodo, nome_turma))
    conn.close()
    return df

def buscar_alunos_da_turma_por_id(turma_id):
    conn = obter_conexao()
    query = '''
        SELECT id, nome_aluno, numero_chamada
        FROM alunos
        WHERE turma_id = ?
        ORDER BY CAST(numero_chamada AS INTEGER), nome_aluno
    '''
    df = pd.read_sql_query(query, conn, params=(turma_id,))
    conn.close()
    return df

def buscar_notas_aluno_com_ids(periodo, nome_turma, nome_aluno):
    conn = obter_conexao()
    query = '''
        SELECT 
            n.id as nota_id,
            d.nome_disciplina as DISCIPLINA,
            n.nota_parcial as NOTA_PARCIAL,
            n.nota_diversificada as NOTA_DIVERSIFICADA,
            n.avaliacao_trimestral as AVALIACAO_TRIMESTRAL,
            n.nota_final as NOTA_FINAL
        FROM notas n
        JOIN alunos a ON n.aluno_id = a.id
        JOIN turmas t ON a.turma_id = t.id
        JOIN disciplinas d ON n.disciplina_id = d.id
        WHERE n.periodo = ? AND t.nome_turma = ? AND a.nome_aluno = ?
        ORDER BY d.nome_disciplina
    '''
    df = pd.read_sql_query(query, conn, params=(periodo, nome_turma, nome_aluno))
    conn.close()
    return df

def verificar_nota_existente(periodo, nome_turma, nome_aluno, disciplina):
    conn = obter_conexao()
    query = '''
        SELECT 1 FROM notas n
        JOIN alunos a ON n.aluno_id = a.id
        JOIN turmas t ON a.turma_id = t.id
        JOIN disciplinas d ON n.disciplina_id = d.id
        WHERE n.periodo = ? AND t.nome_turma = ? AND a.nome_aluno = ? AND d.nome_disciplina = ?
    '''
    cursor = conn.cursor()
    cursor.execute(query, (periodo, nome_turma, nome_aluno, disciplina))
    existe = cursor.fetchone() is not None
    conn.close()
    return existe

def atualizar_nota_por_id(nota_id, parcial, diversificada, trimestral):
    conn = obter_conexao()
    cursor = conn.cursor()
    nota_final = round(parcial + diversificada + trimestral, 1)
    cursor.execute('''
        UPDATE notas 
        SET nota_parcial = ?, nota_diversificada = ?, avaliacao_trimestral = ?, nota_final = ?
        WHERE id = ?
    ''', (parcial, diversificada, trimestral, nota_final, nota_id))
    conn.commit()
    conn.close()

def deletar_nota_por_id(nota_id):
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM notas WHERE id = ?', (nota_id,))
    conn.commit()
    conn.close()

def deletar_banco():
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS notas")
    cursor.execute("DROP TABLE IF EXISTS alunos")
    cursor.execute("DROP TABLE IF EXISTS disciplinas")
    cursor.execute("DROP TABLE IF EXISTS turmas")
    conn.commit()
    conn.close()