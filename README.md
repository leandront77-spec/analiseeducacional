# Painel de Desempenho Escolar

## Situação do projeto

Protótipo acadêmico em desenvolvimento. Nesta etapa foram implementadas as funcionalidades de cadastro, lançamento, importação e consulta de notas.
O projeto faz parte da disciplina de Projeto de Software e utiliza uma arquitetura composta por interface, regras de processamento e banco de dados relacional.

## Objetivo

Facilitar o trabalho de professores e coordenadores pedagógicos no armazenamento e na consulta das notas dos estudantes, permitindo visualizar o boletim completo de cada aluno por turma e período letivo.

## Funcionalidades

- Cadastro de turmas, alunos e componentes curriculares;
- lançamento individual de notas;
- lançamento coletivo de notas por componente curricular;
- importação de dados por planilha Excel;
- consulta por período, turma e aluno;
- apresentação do boletim completo do estudante;
- alteração de notas cadastradas;
- cálculo automático da nota final;
- armazenamento local dos dados.

## Tecnologias utilizadas

- Python;
- Streamlit;
- SQLite;
- Pandas;
- OpenPyXL.

## Estrutura do projeto

```text
Projeto Facul/
├── app.py
├── controle/
│   ├── __init__.py
│   └── db.py
├── database/
├── .gitignore
├── requirements.txt
└── README.md
```

## Banco de dados

O sistema utiliza um banco de dados relacional SQLite, criado automaticamente na primeira execução.

As principais tabelas são:

- `turmas`: armazena as turmas cadastradas;
- `alunos`: armazena os estudantes e sua turma;
- `disciplinas`: armazena os componentes curriculares;
- `notas`: relaciona alunos, disciplinas e períodos letivos.

O banco utiliza chaves primárias, chaves estrangeiras, restrições de unicidade e exclusão em cascata.

## Como executar

### 1. Clonar o repositório

```bash
git clone https://github.com/leandront77-spec/analiseeducacional.git
```

### 2. Entrar na pasta

```bash
cd analiseeducacional
```

### 3. Criar um ambiente virtual

```bash
python -m venv .venv
```

### 4. Ativar o ambiente virtual

Linux:

```bash
source .venv/bin/activate
```

Windows:

```bash
.venv\Scripts\activate
```

### 5. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 6. Executar o sistema

```bash
streamlit run app.py
```

Depois da execução, o Streamlit abrirá o sistema no navegador.

## Privacidade dos dados

O banco de dados e as planilhas utilizadas não são enviados ao GitHub. O arquivo `.gitignore` impede o versionamento desses arquivos para proteger os dados escolares.

Os dados apresentados na demonstração do projeto serão fictícios ou anonimizados.

## Situação do projeto

Primeira versão funcional, contendo banco de dados relacional, cadastro, importação, lançamento e consulta de notas.

## Autor

Leandro Bozolão Neto