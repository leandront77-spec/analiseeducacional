import sqlite3
import pandas as pd
import os

DB_PATH = os.path.join("database", "escola_relacional.db")

def garantir_pasta_db():
    if not os.path.exists("database"):
        os.makedirs("database")

def inicializar_banco():
    garantir_pasta_db()
    conexao = sqlite3.connect(DB_PATH)
    cursor = conexao.cursor()
    
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
            codigo_matricula TEXT,
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
            nota_parcial REAL,
            nota_diversificada REAL,
            avaliacao_trimestral REAL,
            nota_final REAL,
            FOREIGN KEY (aluno_id) REFERENCES alunos (id) ON DELETE CASCADE,
            FOREIGN KEY (disciplina_id) REFERENCES disciplinas (id) ON DELETE CASCADE,
            UNIQUE(periodo, aluno_id, disciplina_id)
        )
    ''')
    
    conexao.commit()
    conexao.close()

def obter_conexao():
    garantir_pasta_db()
    return sqlite3.connect(DB_PATH)

def buscar_periodos():
    conexao = obter_conexao()
    df = pd.read_sql('SELECT DISTINCT periodo FROM notas ORDER BY periodo', conexao)
    conexao.close()
    return df

def buscar_turmas():
    conexao = obter_conexao()
    df = pd.read_sql('SELECT id, nome_turma FROM turmas ORDER BY nome_turma', conexao)
    conexao.close()
    return df

def buscar_disciplinas():
    conexao = obter_conexao()
    df = pd.read_sql('SELECT id, nome_disciplina FROM disciplinas ORDER BY nome_disciplina', conexao)
    conexao.close()
    return df

def buscar_turmas_por_periodo(periodo):
    conexao = obter_conexao()
    query = '''
        SELECT DISTINCT t.nome_turma 
        FROM turmas t 
        JOIN alunos a ON t.id = a.turma_id 
        JOIN notas n ON a.id = n.aluno_id 
        WHERE n.periodo = ? 
        ORDER BY t.nome_turma
    '''
    df = pd.read_sql(query, conexao, params=(periodo,))
    conexao.close()
    return df

def buscar_alunos_por_turma(periodo, turma):
    conexao = obter_conexao()
    query = '''
        SELECT DISTINCT a.nome_aluno 
        FROM alunos a 
        JOIN turmas t ON a.turma_id = t.id 
        JOIN notas n ON a.id = n.aluno_id 
        WHERE n.periodo = ? AND t.nome_turma = ? 
        ORDER BY a.nome_aluno
    '''
    df = pd.read_sql(query, conexao, params=(periodo, turma))
    conexao.close()
    return df

def buscar_alunos_da_turma_por_id(turma_id):
    conexao = obter_conexao()
    query = '''
        SELECT id, numero_chamada, nome_aluno 
        FROM alunos 
        WHERE turma_id = ? 
        ORDER BY CAST(numero_chamada AS INTEGER) ASC, nome_aluno ASC
    '''
    df = pd.read_sql(query, conexao, params=(turma_id,))
    conexao.close()
    return df

def buscar_notas_aluno_com_ids(periodo, turma, aluno):
    conexao = obter_conexao()
    query = '''
        SELECT n.id as nota_id,
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
    '''
    df = pd.read_sql(query, conexao, params=(periodo, turma, aluno))
    conexao.close()
    return df

def atualizar_nota_por_id(nota_id, parcial, diversificada, trimestral):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    final = parcial + diversificada + trimestral
    cursor.execute('''
        UPDATE notas 
        SET nota_parcial = ?, nota_diversificada = ?, avaliacao_trimestral = ?, nota_final = ?
        WHERE id = ?
    ''', (parcial, diversificada, trimestral, final, nota_id))
    conexao.commit()
    conexao.close()

def deletar_banco():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)