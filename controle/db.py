import sqlite3
import pandas as pd
import os

DB_PATH = "database/desempenho_escolar.db"

def obter_conexao():
    """Retorna uma conexão ativa com o banco de dados SQLite."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conexao = sqlite3.connect(DB_PATH)
    conexao.execute("PRAGMA foreign_keys = ON;")
    return conexao

def inicializar_banco():
    """Cria as tabelas necessárias se elas não existirem."""
    conexao = obter_conexao()
    cursor = conexao.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS turmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_turma TEXT UNIQUE NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alunos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_aluno TEXT NOT NULL,
            numero_chamada TEXT,
            turma_id INTEGER,
            FOREIGN KEY (turma_id) REFERENCES turmas(id) ON DELETE CASCADE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS disciplinas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_disciplina TEXT UNIQUE NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo TEXT NOT NULL,
            aluno_id INTEGER,
            disciplina_id INTEGER,
            nota_parcial REAL,
            nota_diversificada REAL,
            avaliacao_trimestral REAL,
            nota_final REAL,
            FOREIGN KEY (aluno_id) REFERENCES alunos(id) ON DELETE CASCADE,
            FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id) ON DELETE CASCADE
        )
    """)
    
    conexao.commit()
    conexao.close()

def buscar_periodos():
    conexao = obter_conexao()
    df = pd.read_sql_query("SELECT DISTINCT periodo FROM notas ORDER BY periodo", conexao)
    conexao.close()
    return df

def buscar_turmas():
    conexao = obter_conexao()
    df = pd.read_sql_query("SELECT id, nome_turma FROM turmas ORDER BY nome_turma", conexao)
    conexao.close()
    return df

def buscar_disciplinas():
    conexao = obter_conexao()
    df = pd.read_sql_query("SELECT id, nome_disciplina FROM disciplinas ORDER BY nome_disciplina", conexao)
    conexao.close()
    return df

def buscar_turmas_por_periodo(periodo):
    conexao = obter_conexao()
    query = """
        SELECT DISTINCT t.id, t.nome_turma 
        FROM turmas t
        JOIN alunos a ON a.turma_id = t.id
        JOIN notas n ON n.aluno_id = a.id
        WHERE n.periodo = ?
        ORDER BY t.nome_turma
    """
    df = pd.read_sql_query(query, conexao, params=(periodo,))
    conexao.close()
    return df

def buscar_alunos_por_turma(periodo, turma_nome):
    conexao = obter_conexao()
    query = """
        SELECT DISTINCT a.id, a.nome_aluno, a.numero_chamada
        FROM alunos a
        JOIN turmas t ON a.turma_id = t.id
        JOIN notas n ON n.aluno_id = a.id
        WHERE n.periodo = ? AND t.nome_turma = ?
        ORDER BY 
            CASE WHEN a.numero_chamada GLOB '[0-9]*' THEN CAST(a.numero_chamada AS INTEGER) ELSE 9999 END, 
            a.nome_aluno
    """
    df = pd.read_sql_query(query, conexao, params=(periodo, turma_nome))
    conexao.close()
    return df

def buscar_alunos_da_turma_por_id(turma_id):
    conexao = obter_conexao()
    query = """
        SELECT id, nome_aluno, numero_chamada
        FROM alunos
        WHERE turma_id = ?
        ORDER BY 
            CASE WHEN numero_chamada GLOB '[0-9]*' THEN CAST(numero_chamada AS INTEGER) ELSE 9999 END, 
            nome_aluno
    """
    df = pd.read_sql_query(query, conexao, params=(turma_id,))
    conexao.close()
    return df

def buscar_notas_aluno_com_ids(periodo, turma_nome, aluno_nome):
    conexao = obter_conexao()
    query = """
        SELECT 
            n.id as nota_id,
            d.nome_disciplina AS DISCIPLINA,
            n.nota_parcial AS NOTA_PARCIAL,
            n.nota_diversificada AS NOTA_DIVERSIFICADA,
            n.avaliacao_trimestral AS AVALIACAO_TRIMESTRAL,
            n.nota_final AS NOTA_FINAL
        FROM notas n
        JOIN alunos a ON n.aluno_id = a.id
        JOIN turmas t ON a.turma_id = t.id
        JOIN disciplinas d ON n.disciplina_id = d.id
        WHERE n.periodo = ? AND t.nome_turma = ? AND a.nome_aluno = ?
        ORDER BY d.nome_disciplina
    """
    df = pd.read_sql_query(query, conexao, params=(periodo, turma_nome, aluno_nome))
    conexao.close()
    return df

def verificar_nota_existente(periodo, turma_nome, aluno_nome, disciplina_nome):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    query = """
        SELECT n.id 
        FROM notas n
        JOIN alunos a ON n.aluno_id = a.id
        JOIN turmas t ON a.turma_id = t.id
        JOIN disciplinas d ON n.disciplina_id = d.id
        WHERE n.periodo = ? AND t.nome_turma = ? AND a.nome_aluno = ? AND d.nome_disciplina = ?
    """
    cursor.execute(query, (periodo, turma_nome, aluno_nome, disciplina_nome))
    res = cursor.fetchone()
    conexao.close()
    return res is not None

def atualizar_nota_por_id(nota_id, parcial, diversificada, trimestral):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    nota_final = round(parcial + diversificada + trimestral, 1)
    cursor.execute("""
        UPDATE notas 
        SET nota_parcial = ?, nota_diversificada = ?, avaliacao_trimestral = ?, nota_final = ?
        WHERE id = ?
    """, (parcial, diversificada, trimestral, nota_final, nota_id))
    conexao.commit()
    conexao.close()

def deletar_nota_por_id(nota_id):
    conexao = obter_conexao()
    cursor = conexao.cursor()
    cursor.execute("DELETE FROM notas WHERE id = ?", (nota_id,))
    conexao.commit()
    conexao.close()

def buscar_media_por_disciplina(periodo, turma_nome):
    """Calcula a média geral da sala por componente curricular para a AC3."""
    conexao = obter_conexao()
    query = """
        SELECT 
            d.nome_disciplina AS DISCIPLINA,
            ROUND(AVG(n.nota_final), 1) AS MEDIA_TURMA,
            COUNT(n.id) AS TOTAL_AVALIADOS
        FROM notas n
        JOIN alunos a ON n.aluno_id = a.id
        JOIN turmas t ON a.turma_id = t.id
        JOIN disciplinas d ON n.disciplina_id = d.id
        WHERE n.periodo = ? AND t.nome_turma = ?
        GROUP BY d.nome_disciplina
        ORDER BY d.nome_disciplina;
    """
    df = pd.read_sql_query(query, conexao, params=(periodo, turma_nome))
    conexao.close()
    return df

def buscar_resumo_turma(periodo, turma_nome):
    """Retorna a média geral e o total de alunos da turma no período."""
    conexao = obter_conexao()
    query = """
        SELECT 
            ROUND(AVG(n.nota_final), 1) AS MEDIA_GERAL,
            COUNT(DISTINCT a.id) AS TOTAL_ALUNOS
        FROM notas n
        JOIN alunos a ON n.aluno_id = a.id
        JOIN turmas t ON a.turma_id = t.id
        WHERE n.periodo = ? AND t.nome_turma = ?
    """
    df = pd.read_sql_query(query, conexao, params=(periodo, turma_nome))
    conexao.close()
    return df

def buscar_alunos_abaixo_media(periodo, turma_nome, nota_corte):
    """Lista os alunos com pelo menos uma disciplina abaixo da nota de corte, com a média do aluno."""
    conexao = obter_conexao()
    query = """
        SELECT 
            a.numero_chamada AS CHAMADA,
            a.nome_aluno AS ALUNO,
            ROUND(AVG(n.nota_final), 1) AS MEDIA_ALUNO,
            SUM(CASE WHEN n.nota_final < ? THEN 1 ELSE 0 END) AS QTD_DISCIPLINAS,
            GROUP_CONCAT(CASE WHEN n.nota_final < ? THEN d.nome_disciplina END, ', ') AS DISCIPLINAS,
            ROUND(MIN(n.nota_final), 1) AS MENOR_NOTA
        FROM notas n
        JOIN alunos a ON n.aluno_id = a.id
        JOIN turmas t ON a.turma_id = t.id
        JOIN disciplinas d ON n.disciplina_id = d.id
        WHERE n.periodo = ? AND t.nome_turma = ?
        GROUP BY a.id, a.numero_chamada, a.nome_aluno
        HAVING QTD_DISCIPLINAS > 0
        ORDER BY MEDIA_ALUNO, QTD_DISCIPLINAS DESC, a.nome_aluno
    """
    df = pd.read_sql_query(query, conexao, params=(nota_corte, nota_corte, periodo, turma_nome))
    conexao.close()
    return df

def buscar_medias_disciplina_por_trimestre(turma_nome):
    """Retorna a média da turma em cada disciplina e em cada trimestre (comparativo)."""
    conexao = obter_conexao()
    query = """
        SELECT 
            d.nome_disciplina AS DISCIPLINA,
            n.periodo AS PERIODO,
            ROUND(AVG(n.nota_final), 1) AS MEDIA
        FROM notas n
        JOIN alunos a ON n.aluno_id = a.id
        JOIN turmas t ON a.turma_id = t.id
        JOIN disciplinas d ON n.disciplina_id = d.id
        WHERE t.nome_turma = ?
        GROUP BY d.nome_disciplina, n.periodo
        ORDER BY d.nome_disciplina, n.periodo
    """
    df = pd.read_sql_query(query, conexao, params=(turma_nome,))
    conexao.close()
    return df

def buscar_resumo_turma_por_trimestre(turma_nome, nota_corte):
    """Retorna, para cada trimestre, a média geral da turma e quantos alunos ficaram com média abaixo do corte."""
    conexao = obter_conexao()
    query = """
        SELECT 
            PERIODO,
            ROUND(AVG(MEDIA_ALUNO), 1) AS MEDIA_GERAL,
            COUNT(*) AS TOTAL_ALUNOS,
            SUM(CASE WHEN MEDIA_ALUNO < ? THEN 1 ELSE 0 END) AS ALUNOS_ABAIXO
        FROM (
            SELECT n.periodo AS PERIODO, a.id AS ALUNO_ID, AVG(n.nota_final) AS MEDIA_ALUNO
            FROM notas n
            JOIN alunos a ON n.aluno_id = a.id
            JOIN turmas t ON a.turma_id = t.id
            WHERE t.nome_turma = ?
            GROUP BY n.periodo, a.id
        )
        GROUP BY PERIODO
        ORDER BY PERIODO
    """
    df = pd.read_sql_query(query, conexao, params=(nota_corte, turma_nome))
    conexao.close()
    return df

def buscar_alunos_da_turma_por_nome(turma_nome):
    conexao = obter_conexao()
    query = """
        SELECT a.id, a.nome_aluno, a.numero_chamada
        FROM alunos a
        JOIN turmas t ON a.turma_id = t.id
        WHERE t.nome_turma = ?
        ORDER BY 
            CASE WHEN a.numero_chamada GLOB '[0-9]*' THEN CAST(a.numero_chamada AS INTEGER) ELSE 9999 END, 
            a.nome_aluno
    """
    df = pd.read_sql_query(query, conexao, params=(turma_nome,))
    conexao.close()
    return df

def buscar_notas_aluno_por_trimestre(turma_nome, aluno_nome):
    """Retorna a nota final do aluno em cada disciplina e trimestre (comparativo)."""
    conexao = obter_conexao()
    query = """
        SELECT 
            d.nome_disciplina AS DISCIPLINA,
            n.periodo AS PERIODO,
            n.nota_final AS NOTA_FINAL
        FROM notas n
        JOIN alunos a ON n.aluno_id = a.id
        JOIN turmas t ON a.turma_id = t.id
        JOIN disciplinas d ON n.disciplina_id = d.id
        WHERE t.nome_turma = ? AND a.nome_aluno = ?
        ORDER BY d.nome_disciplina, n.periodo
    """
    df = pd.read_sql_query(query, conexao, params=(turma_nome, aluno_nome))
    conexao.close()
    return df

def buscar_turmas_com_resumo():
    """Lista as turmas com a quantidade de alunos e os trimestres que possuem notas."""
    conexao = obter_conexao()
    query = """
        SELECT 
            t.id,
            t.nome_turma AS TURMA,
            COUNT(DISTINCT a.id) AS QTD_ALUNOS,
            (SELECT GROUP_CONCAT(periodo, ', ') FROM (
                SELECT DISTINCT n2.periodo AS periodo
                FROM notas n2
                JOIN alunos a2 ON n2.aluno_id = a2.id
                WHERE a2.turma_id = t.id
                ORDER BY n2.periodo
            )) AS TRIMESTRES
        FROM turmas t
        LEFT JOIN alunos a ON a.turma_id = t.id
        GROUP BY t.id, t.nome_turma
        ORDER BY t.nome_turma
    """
    df = pd.read_sql_query(query, conexao)
    conexao.close()
    return df

def contar_alunos_em_comum(turma_origem_id, turma_destino_id):
    """Conta quantos alunos (pelo nome) existem nas duas turmas."""
    conexao = obter_conexao()
    cursor = conexao.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM alunos a1
        JOIN alunos a2 ON a1.nome_aluno = a2.nome_aluno
        WHERE a1.turma_id = ? AND a2.turma_id = ?
    """, (turma_origem_id, turma_destino_id))
    qtd = cursor.fetchone()[0]
    conexao.close()
    return qtd

def renomear_ou_unir_turma(turma_origem_id, novo_nome):
    """
    Corrige o nome de uma turma.
    - Se o novo nome não existir, apenas renomeia a turma.
    - Se já existir outra turma com esse nome, une as duas: os alunos e as notas
      passam para a turma existente. Alunos com o mesmo nome são unificados e,
      se houver nota no mesmo trimestre e disciplina, fica a nota da turma corrigida.
    Retorna "renomeada" ou "unida".
    """
    novo_nome = novo_nome.strip().upper()
    conexao = obter_conexao()
    cursor = conexao.cursor()
    
    cursor.execute("SELECT id FROM turmas WHERE nome_turma = ?", (novo_nome,))
    res = cursor.fetchone()
    
    if res is None or res[0] == turma_origem_id:
        cursor.execute("UPDATE turmas SET nome_turma = ? WHERE id = ?", (novo_nome, turma_origem_id))
        conexao.commit()
        conexao.close()
        return "renomeada"
    
    turma_destino_id = res[0]
    cursor.execute("SELECT id, nome_aluno FROM alunos WHERE turma_id = ?", (turma_origem_id,))
    alunos_origem = cursor.fetchall()
    
    for aluno_origem_id, nome_aluno in alunos_origem:
        cursor.execute("SELECT id FROM alunos WHERE turma_id = ? AND nome_aluno = ?", (turma_destino_id, nome_aluno))
        aluno_destino = cursor.fetchone()
        
        if aluno_destino is None:
            # Aluno só existe na turma corrigida: apenas muda de turma
            cursor.execute("UPDATE alunos SET turma_id = ? WHERE id = ?", (turma_destino_id, aluno_origem_id))
        else:
            # Aluno existe nas duas: passa as notas para o cadastro da turma de destino
            aluno_destino_id = aluno_destino[0]
            cursor.execute("SELECT id, periodo, disciplina_id FROM notas WHERE aluno_id = ?", (aluno_origem_id,))
            for nota_id, periodo, disciplina_id in cursor.fetchall():
                cursor.execute("DELETE FROM notas WHERE aluno_id = ? AND periodo = ? AND disciplina_id = ?", (aluno_destino_id, periodo, disciplina_id))
                cursor.execute("UPDATE notas SET aluno_id = ? WHERE id = ?", (aluno_destino_id, nota_id))
            cursor.execute("DELETE FROM alunos WHERE id = ?", (aluno_origem_id,))
    
    cursor.execute("DELETE FROM turmas WHERE id = ?", (turma_origem_id,))
    conexao.commit()
    conexao.close()
    return "unida"

def buscar_base_analise():
    """Retorna todas as notas finais com período, turma e disciplina (base para os filtros e gráficos da AC4)."""
    conexao = obter_conexao()
    query = """
        SELECT 
            n.periodo AS PERIODO,
            t.nome_turma AS TURMA,
            d.nome_disciplina AS COMPONENTE,
            a.id AS ALUNO_ID,
            n.nota_final AS NOTA_FINAL
        FROM notas n
        JOIN alunos a ON n.aluno_id = a.id
        JOIN turmas t ON a.turma_id = t.id
        JOIN disciplinas d ON n.disciplina_id = d.id
    """
    df = pd.read_sql_query(query, conexao)
    conexao.close()
    return df

def deletar_banco():
    """Apaga as tabelas do banco (evita erro de arquivo em uso no Windows)."""
    conexao = obter_conexao()
    cursor = conexao.cursor()
    cursor.execute("DROP TABLE IF EXISTS notas")
    cursor.execute("DROP TABLE IF EXISTS alunos")
    cursor.execute("DROP TABLE IF EXISTS disciplinas")
    cursor.execute("DROP TABLE IF EXISTS turmas")
    conexao.commit()
    conexao.close()