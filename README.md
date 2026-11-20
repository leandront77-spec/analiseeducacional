# Painel de Desempenho Escolar

Sistema local desenvolvido como projeto acadêmico para cadastro, armazenamento, consulta e análise de dados de desempenho escolar.

O trabalho tem como foco a modelagem do banco de dados, a organização das funcionalidades e a integração entre uma interface em Streamlit, o processamento em Python e um banco SQLite.

## Objetivo


Facilitar o trabalho de professores e coordenadores pedagógicos no armazenamento e na consulta das notas dos estudantes, permitindo visualizar o boletim completo de cada aluno, acompanhar a média final anual e comparar o desempenho entre trimestres, séries, turmas e componentes curriculares.

## Funcionalidades

- Cadastro de turmas, alunos e componentes curriculares;
- lançamento individual de notas;
- lançamento coletivo de notas por componente curricular;
- importação de dados por planilha Excel;
- consulta por período, turma e aluno;
- apresentação do boletim completo do estudante;
- alteração de notas cadastradas;
- cálculo automático da nota final;
- armazenamento local dos dados;
- correção do nome de turmas e união de turmas importadas com nome errado;
- panorama da turma com média por componente e lista de alunos abaixo da média;
- comparativo da turma e do aluno entre os trimestres;
- média final anual ponderada (pesos configuráveis por trimestre) com a situação do aluno;
- análises com filtros por trimestre, série, turma e componente curricular;
- gráficos comparativos entre turmas, séries e componentes, e evolução nos trimestres;
- exportação dos dados filtrados em CSV.

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

Caso o comando `streamlit` não seja reconhecido (comum no Windows), execute:

```bash
python -m streamlit run app.py
```

Para testar, importe as planilhas fictícias da pasta `Dados` em **Cadastro > Importar Planilha**, escolhendo o trimestre correspondente a cada arquivo.

## Privacidade dos dados

O banco de dados não é enviado ao GitHub. O arquivo `.gitignore` impede o versionamento dos arquivos do banco e de planilhas reais, para proteger os dados escolares.

As planilhas da pasta `Dados` contêm apenas dados fictícios/anonimizados, usados para demonstração.

## Situação do projeto

Versão final do projeto acadêmico, entregue em quatro etapas:

- **AC1 e AC2:** cadastro, lançamento, importação e consulta de notas;
- **AC3:** panorama da turma, comparativo entre trimestres, média final ponderada e correção de turmas;
- **AC4:** módulo de Análises e Gráficos, com filtros e comparações entre séries, turmas e componentes curriculares.

## Autor

Leandro Bozolão Neto