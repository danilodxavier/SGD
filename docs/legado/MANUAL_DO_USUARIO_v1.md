> **Documento histórico (v1).** Substituído pelo manual do SAD-GD em `docs/`. Mantido para referência.

# Manual do Usuário — Agente de Inteligência Documental

| | |
|---|---|
| **Sistema** | Agente de Inteligência Documental — Contratos e Checklists |
| **Versão documentada** | 1.0.0 |
| **Data de criação deste manual** | 14/10/2026 |
| **Público** | Todas as pessoas que usam o sistema, inclusive quem nunca o usou |

> Este manual explica **como usar** o sistema. Instalação, configuração do servidor, backup e solução de problemas
> técnicos estão no [Manual Técnico](MANUAL_TECNICO_v1.md).

## Sumário

1. [Apresentação](#1-apresentação)
2. [Requisitos de acesso](#2-requisitos-de-acesso)
3. [Primeiro acesso](#3-primeiro-acesso)
   - [3.1 Configuração inicial (somente na instalação)](#31-configuração-inicial-somente-na-instalação)
   - [3.2 Entrar no sistema](#32-entrar-no-sistema)
   - [3.3 Trocar a senha temporária](#33-trocar-a-senha-temporária)
   - [3.4 Alterar a senha a qualquer momento](#34-alterar-a-senha-a-qualquer-momento)
   - [3.5 Esqueci minha senha](#35-esqueci-minha-senha)
   - [3.6 Sair do sistema](#36-sair-do-sistema)
4. [Visão geral da tela](#4-visão-geral-da-tela)
5. [Funcionalidades](#5-funcionalidades)
   - [5.1 Painel](#51-painel)
   - [5.2 Fazer perguntas sobre os documentos](#52-fazer-perguntas-sobre-os-documentos)
   - [5.3 Consultar documentos](#53-consultar-documentos)
   - [5.4 Checklist](#54-checklist)
   - [5.5 Relatórios](#55-relatórios)
   - [5.6 Usuários (administradores)](#56-usuários-administradores)
   - [5.7 Configurações (administradores)](#57-configurações-administradores)
6. [Perfis e permissões](#6-perfis-e-permissões)
7. [Perguntas frequentes](#7-perguntas-frequentes)
8. [Resolução de problemas comuns](#8-resolução-de-problemas-comuns)
9. [Glossário](#9-glossário)

---

## 1. Apresentação

### O que é

O **Agente de Inteligência Documental** é um sistema que **lê os documentos de contratos** guardados em uma pasta do
computador (contratos, termos aditivos, planilhas, certidões, portarias, notas fiscais etc.) e permite:

- **fazer perguntas em português**, como *"Quando encerra o contrato 034/2022?"*, e receber a resposta com a
  indicação exata de onde ela foi encontrada (documento e página);
- **conferir checklists**, ou seja, listas de documentos exigidos, e ver o que está atendido, ausente ou vencido;
- **gerar relatórios** em PDF, Word, Excel e outros formatos.

### Para que serve

Para economizar tempo na conferência de processos e contratos e **evitar erros**. O sistema:

- **nunca inventa informação**: se algo não estiver nos documentos, ele responde *"Não localizei essa informação nos
  documentos disponibilizados."*;
- **mostra sempre a fonte** (documento, página, trecho), para que você possa conferir;
- **avisa quando documentos discordam entre si** (por exemplo, dois valores diferentes para o mesmo contrato) e não
  escolhe sozinho qual está certo;
- **nunca altera, move ou apaga** os documentos originais.

### Quem usa

| Quem | O que faz |
|---|---|
| **Usuários de Consulta** | Fazem perguntas, consultam documentos, criam e executam checklists e geram relatórios. |
| **Administradores** | Tudo o que o perfil Consulta faz e, além disso, cadastram usuários, escolhem a pasta de documentos, atualizam o índice e ajustam configurações. |

---

## 2. Requisitos de acesso

### Navegador recomendado

Use um destes navegadores, **atualizado**:

- **Microsoft Edge** (já vem instalado no Windows) — recomendado;
- Google Chrome;
- Mozilla Firefox.

> O que é um navegador? É o programa usado para abrir sites (por exemplo, o Edge, com o ícone de uma onda azul e
> verde). O sistema funciona dentro do navegador, mas **não é um site da Internet**: ele roda em um computador da
> própria instituição.

### Endereço de acesso

O endereço é diferente conforme o computador de onde você acessa:

| De onde você acessa | Endereço a digitar na barra de endereços do navegador |
|---|---|
| Do **próprio computador onde o sistema está instalado** | `http://127.0.0.1:8000` |
| De **outro computador da rede** | `http://NOME_DO_COMPUTADOR:8000` — `[VERIFICAR: endereço definitivo a ser informado pela TI depois de liberar o acesso pela rede; se a TI configurar HTTPS, o endereço começará com https://]` |

Como digitar o endereço:

1. Abra o navegador.
2. Clique na **barra de endereços**, a faixa comprida no alto da janela onde aparecem endereços de sites.
3. Apague o que estiver escrito.
4. Digite o endereço exatamente como na tabela, sem espaços.
5. Pressione a tecla **Enter**.

> 💡 Dica: depois que a página abrir, adicione-a aos favoritos (tecla **Ctrl + D**) para não precisar digitar de novo.

> ⚠️ ATENÇÃO: o sistema só funciona **enquanto o computador onde ele está instalado estiver ligado e com o sistema em
> execução**. Se a página não abrir, veja a seção [8. Resolução de problemas comuns](#8-resolução-de-problemas-comuns).

### Como obter um login

Peça a um **administrador do sistema** que crie o seu usuário. Ele vai informar:

- o seu **nome de usuário** (por exemplo, `maria.silva`);
- uma **senha temporária**, que você trocará no primeiro acesso.

Os contatos dos administradores estão na tabela de contatos do [Manual Técnico](MANUAL_TECNICO_v1.md#11-contatos-e-acessos).
`[VERIFICAR: informar aqui o setor ou a pessoa responsável por criar usuários]`

> **Não se aplica:** o sistema **não usa** o login do Windows, da rede ou do e-mail institucional (@sema.mt.gov.br).
> O usuário e a senha são próprios deste sistema.

---

## 3. Primeiro acesso

### 3.1 Configuração inicial (somente na instalação)

**Objetivo:** criar o primeiro administrador logo depois que o sistema é instalado.

**Quem faz:** a pessoa responsável pela instalação, **sentada no computador onde o sistema está instalado**. Esta tela
aparece **uma única vez**: quando ainda não existe nenhum usuário cadastrado.

1. No computador onde o sistema está instalado, abra o navegador e acesse `http://127.0.0.1:8000`.
2. Aparece a tela **Configuração inicial**.

   > 📷 [CAPTURA DE TELA: tela "Configuração inicial" sobre fundo azul, com os campos Usuário, Nome completo, Senha,
   > Repita a senha e o botão "Criar administrador e entrar"]

3. No campo **Usuário**, digite o nome de usuário do administrador (veja as regras abaixo).
4. No campo **Nome completo**, digite o nome da pessoa.
5. No campo **Senha**, digite uma senha (veja as regras abaixo).
6. No campo **Repita a senha**, digite a mesma senha novamente.
7. Clique no botão **Criar administrador e entrar**.

| Campo | O que preencher | Obrigatório | Regras | Exemplo |
|---|---|---|---|---|
| Usuário | Nome que será usado para entrar | Sim | De 3 a 50 caracteres; somente letras **minúsculas sem acento**, números, ponto (`.`), hífen (`-`) ou sublinhado (`_`); deve começar com letra ou número | `maria.silva` |
| Nome completo | Nome da pessoa | Sim | Até 120 caracteres | `Maria da Silva` |
| Senha | Senha de acesso | Sim | Pelo menos 8 caracteres, com **letras e números**; não pode ser igual ao usuário | `Contratos2026` (apenas exemplo — não use) |
| Repita a senha | A mesma senha | Sim | Igual ao campo Senha | — |

**O que acontece depois:** aparece a mensagem *"Administrador criado. Bem-vindo(a)!"* e o sistema abre já com você
conectado, na tela **Painel**.

**Erros possíveis:**

| Mensagem | O que significa | Como resolver |
|---|---|---|
| As senhas digitadas não conferem. | Os campos Senha e Repita a senha estão diferentes. | Digite a mesma senha nos dois campos. |
| Usuário inválido: use de 3 a 50 caracteres, apenas letras minúsculas sem acento… | O usuário tem espaço, acento, letra maiúscula ou símbolo não permitido. | Use, por exemplo, `maria.silva`. |
| A senha deve ter pelo menos 8 caracteres. | Senha curta demais. | Use 8 ou mais caracteres. |
| A senha deve conter letras e números. | Faltam letras ou números. | Misture letras e números, por exemplo `Contratos2026`. |
| A senha não pode ser igual ao nome de usuário. | Senha igual ao usuário. | Escolha outra senha. |
| Esta função só pode ser usada no computador onde o sistema está instalado. | Você tentou pela rede. | Faça a configuração inicial no computador onde o sistema está instalado. |
| O sistema já foi configurado. Faça login. | O primeiro administrador já existe. | Entre normalmente (seção 3.2). |

> Se você abrir o sistema **de outro computador** antes da configuração inicial, verá a tela **Sistema ainda não
> configurado**. Isso é normal: a configuração inicial só pode ser feita no computador onde o sistema está instalado.

### 3.2 Entrar no sistema

**Objetivo:** identificar-se para usar o sistema.

**Quem pode:** qualquer pessoa com usuário cadastrado e ativo.

1. Abra o navegador e acesse o endereço do sistema (seção 2).
2. Aparece a tela **Entrar**.

   > 📷 [CAPTURA DE TELA: tela "Entrar" sobre fundo azul, com o logotipo "AD", os campos Usuário e Senha e o botão
   > "Entrar"]

3. No campo **Usuário**, digite o seu nome de usuário (letras maiúsculas ou minúsculas tanto faz).
4. No campo **Senha**, digite a sua senha (aqui maiúsculas e minúsculas **fazem diferença**).
5. Clique em **Entrar** (ou pressione **Enter**).

**O que acontece depois:**

- se for o seu **primeiro acesso** (senha temporária), o sistema pede a troca da senha (seção 3.3);
- nos demais acessos, abre a última tela que você usou ou o **Painel**.

Você permanece conectado por **8 horas**. Depois disso, o sistema pede o login novamente.
`[VERIFICAR: a duração pode ter sido alterada pela TI na configuração SESSION_HOURS]`

**Erros possíveis:**

| Mensagem | O que significa | Como resolver |
|---|---|---|
| Usuário ou senha inválidos. | O usuário não existe ou a senha está errada. Por segurança, o sistema não diz qual dos dois. | Confira se a tecla **Caps Lock** está desligada e digite de novo. Se não lembrar a senha, veja a seção 3.5. |
| Conta bloqueada temporariamente por excesso de tentativas. Tente novamente após HH:MM ou peça a um administrador para desbloqueá-la. | Foram digitadas **5 senhas erradas seguidas**. | Aguarde **15 minutos** ou peça a um administrador para desbloquear. |
| Usuário desativado. Procure um administrador do sistema. | O seu acesso foi desligado. | Procure um administrador. |
| Este computador não está autorizado a acessar o sistema. | O computador de onde você acessa não está na lista de computadores permitidos. | Procure a TI. |
| Não foi possível comunicar com o servidor. Verifique se o sistema está em execução. | O computador do sistema está desligado ou o sistema não está rodando. | Veja a seção 8. |

### 3.3 Trocar a senha temporária

**Objetivo:** substituir a senha recebida do administrador por uma senha que só você conhece.

**Quando acontece:** no primeiro acesso e sempre que um administrador redefinir a sua senha. Enquanto você não trocar,
o sistema não deixa usar nenhuma outra função.

1. Depois de entrar com a senha temporária, aparece a tela **Alterar senha**, com a mensagem *"Por segurança, troque a
   senha temporária recebida antes de continuar."*

   > 📷 [CAPTURA DE TELA: tela "Alterar senha" com os campos Senha atual, Nova senha, Repita a nova senha e o botão
   > "Salvar nova senha"]

2. No campo **Senha atual**, digite a senha temporária que você recebeu.
3. No campo **Nova senha**, digite a sua nova senha.
4. No campo **Repita a nova senha**, digite a nova senha novamente.
5. Clique em **Salvar nova senha**.

| Campo | O que preencher | Obrigatório | Regras |
|---|---|---|---|
| Senha atual | A senha temporária (ou a atual) | Sim | — |
| Nova senha | A senha que você vai usar | Sim | Pelo menos 8 caracteres, com letras e números; diferente da atual; diferente do usuário |
| Repita a nova senha | A mesma nova senha | Sim | Igual à nova senha |

**O que acontece depois:** aparece *"Senha alterada com sucesso."* e o sistema abre normalmente.

**Erros possíveis:**

| Mensagem | O que significa | Como resolver |
|---|---|---|
| A senha atual está incorreta. | A senha digitada em "Senha atual" está errada. | Digite a senha temporária exatamente como recebeu. |
| As novas senhas digitadas não conferem. | "Nova senha" e "Repita a nova senha" estão diferentes. | Digite a mesma senha nos dois campos. |
| A nova senha deve ser diferente da atual. | Você repetiu a senha atual. | Escolha outra senha. |
| A senha deve ter pelo menos 8 caracteres. / A senha deve conter letras e números. | A nova senha não segue as regras. | Ajuste conforme a tabela acima. |

> 💡 Dicas para uma boa senha: use uma frase curta com números, no estilo de `Contrato7Verde2026` (apenas o
> estilo — não use este exemplo). Não use datas de
> aniversário, o seu nome ou senhas de outros sistemas. **Nunca anote a senha em papel colado no monitor.**

### 3.4 Alterar a senha a qualquer momento

1. Na barra lateral (à esquerda), abaixo do seu nome, clique em **Alterar senha**.
2. Siga os passos 2 a 5 da seção 3.3.
3. Se desistir, clique em **Cancelar**.

### 3.5 Esqueci minha senha

O sistema **não envia senha por e-mail**.

> **Não se aplica:** não existe recuperação de senha por e-mail ou link. A senha é redefinida por um administrador.

1. Procure um **administrador do sistema**.
2. O administrador vai redefinir a sua senha e informar uma **senha temporária**, pessoalmente.
3. Entre com a senha temporária (seção 3.2).
4. Troque a senha (seção 3.3).

### 3.6 Sair do sistema

**Quando sair:** sempre que terminar de usar, principalmente em computadores compartilhados.

1. Na barra lateral, abaixo do seu nome, clique em **Sair**.
2. Aparece a tela **Entrar** com a mensagem *"Você saiu do sistema."*

---

## 4. Visão geral da tela

Depois de entrar, a tela tem duas partes: a **barra lateral** (faixa azul-escura à esquerda) e a **área principal**
(à direita).

> 📷 [CAPTURA DE TELA: tela inteira do sistema após o login, com a barra lateral à esquerda (logotipo "AD", menus
> Painel, Perguntas, Documentos, Checklist, Relatórios, Usuários, Configurações, nome do usuário, botões "Alterar
> senha" e "Sair", ponto colorido "Sistema operacional") e a tela Painel à direita]

### Barra lateral

| Item | Para que serve | Quem vê |
|---|---|---|
| **Painel** | Resumo da situação: quantos documentos, contratos, erros. | Todos |
| **Perguntas** | Fazer perguntas sobre os contratos. | Todos |
| **Documentos** | Ver a lista de documentos lidos pelo sistema. | Todos |
| **Checklist** | Conferir listas de documentos exigidos. | Todos |
| **Relatórios** | Gerar e baixar relatórios. | Todos |
| **Usuários** | Cadastrar e gerenciar usuários. | Somente administradores |
| **Configurações** | Pasta de documentos, indexação, OCR, IA, verificação e registros. | Somente administradores |
| Seu nome e perfil | Mostra quem está conectado (ex.: `maria.silva · Consulta`). | Todos |
| **Alterar senha** | Troca a sua senha (seção 3.4). | Todos |
| **Sair** | Encerra o seu acesso (seção 3.6). | Todos |
| Ponto colorido | Situação do sistema (tabela abaixo). | Todos |

| Ponto | Texto | Significado |
|---|---|---|
| 🟢 Verde | Sistema operacional | Tudo funcionando. |
| 🟡 Amarelo | Diretório documental indisponível | A pasta onde ficam os documentos não foi encontrada. Avise um administrador. |
| 🔴 Vermelho | Verifique o sistema / Servidor indisponível | Há um problema no sistema ou ele está fora do ar. Veja a seção 8. |

### Avisos na tela

Mensagens curtas aparecem por alguns segundos no **canto inferior direito**:

- fundo **escuro**: confirmação (exemplo: *"Senha alterada com sucesso."*);
- fundo **vermelho**: erro, com a explicação do problema.

### Botões que só aparecem em algumas situações

- **Abrir** e **Abrir no Windows** só aparecem para quem está **no computador onde o sistema está instalado**, porque
  abrem o arquivo nesse computador. Pela rede, use **Visualizar**.
- **Atualizar índice**, **Reindexar este documento** e o menu **Configurações** só aparecem para **administradores**.

---

## 5. Funcionalidades

### 5.1 Painel

**Objetivo:** ver, num só lugar, a situação dos documentos e dos contratos.

**Quem pode usar:** todos. O botão **Atualizar índice** é só para administradores.

1. Na barra lateral, clique em **Painel**.

> 📷 [CAPTURA DE TELA: tela Painel com os cartões numéricos (Documentos encontrados, Documentos indexados, Documentos
> com erro etc.), a tabela "Contratos identificados" e o quadro "Última indexação"]

**O que cada cartão mostra:**

| Cartão | Significado |
|---|---|
| Documentos encontrados | Quantos arquivos existem na pasta de documentos. |
| Documentos indexados | Quantos foram lidos com sucesso e já podem ser pesquisados. |
| Documentos com erro | Arquivos danificados ou protegidos por senha (não puderam ser lidos). |
| Sem texto (requer OCR) | Documentos digitalizados (fotos ou escaneados) ainda sem texto reconhecido. |
| Formato não suportado | Arquivos de tipos que o sistema não lê (ex.: desenhos técnicos). |
| Contratos identificados | Quantos contratos diferentes o sistema reconheceu. |
| Checklists | Quantos checklists foram cadastrados. |
| Última atualização | Data e hora da última leitura da pasta. |
| Indexador | "Em execução" (lendo documentos) ou "Parado". |

**Tabela "Contratos identificados":** número do contrato, contratada (com CNPJ), valor, vigência e o documento de onde
os dados foram tirados. Clique no nome do documento para abri-lo. Esses dados vêm do **termo de contrato original**:
aditivos posteriores podem tê-los alterado, e para a situação atualizada, pergunte na tela **Perguntas**.

**Atualizar índice (administradores):**

1. Clique em **Atualizar índice**.
2. Aparece *"Indexação iniciada."* e uma barra azul mostra o progresso (*"Indexando… X de Y arquivos"*).
3. Aguarde a barra desaparecer. Os números do painel são atualizados sozinhos.

| Mensagem | Significado | Como resolver |
|---|---|---|
| Já existe uma indexação em andamento. | Outra leitura já está acontecendo. | Aguarde a barra de progresso terminar. |
| O diretório … não existe. | A pasta configurada não foi encontrada. | Veja a seção 5.7 (Diretório documental). |

### 5.2 Fazer perguntas sobre os documentos

**Objetivo:** obter respostas sobre os contratos, com a indicação de onde a informação está.

**Quem pode usar:** todos.

1. Na barra lateral, clique em **Perguntas**.
2. Clique no campo **Digite sua pergunta...**.
3. Escreva a pergunta em português (até 1.000 caracteres).
4. Clique em **Pesquisar** (ou pressione **Enter**).
5. Aguarde a resposta aparecer logo abaixo (normalmente em menos de um segundo; com IA local, alguns segundos).

> 📷 [CAPTURA DE TELA: tela Perguntas com a pergunta "Quando encerra o contrato 034/2022?" e o quadro de resposta com
> a etiqueta "Inferência documental", a confiança, o texto da resposta e a lista "Fontes" com os botões
> "Visualizar"]

**Atalho:** abaixo do campo há **exemplos de perguntas** (botões arredondados). Clique em um para perguntá-lo na hora.

**Perguntas que o sistema entende bem** (sempre que possível, **informe o número do contrato**):

| Assunto | Exemplos |
|---|---|
| Vigência | "Quando encerra o contrato 034/2022?", "Qual é a vigência do contrato 034/2022?", "Quando começa a vigência?" |
| Valores | "Qual o valor do contrato 034/2022?", "Qual o valor atualizado?" |
| Partes | "Quem é a contratada?", "Qual o CNPJ da contratada?" |
| Dados gerais | "Qual é o objeto do contrato?", "Qual a data de assinatura?", "Qual o número do processo?" |
| Aditivos | "Quais termos aditivos existem?", "Qual foi o último aditivo?" |
| Itens | "Quais são os itens do contrato 034/2022?" |
| Cláusulas | "Qual a forma de pagamento?", "Quais são as penalidades?", "Como é feita a fiscalização?", "Há cláusula de reajuste?" |
| Documentos | "Quais documentos comprovam a vigência?", "Quais documentos estão relacionados ao contrato 034/2022?" |

Perguntas livres também são aceitas: o sistema mostra os trechos dos documentos que tratam do assunto.

**Como ler a resposta:**

1. **Etiqueta colorida** — o tipo de resposta:

| Etiqueta | O que significa | O que fazer |
|---|---|---|
| **Fato documental** (verde) | A informação está escrita nos documentos e todos concordam. | Pode usar; confira a fonte se for importante. |
| **Inferência documental** (azul) | A conclusão vem da **relação entre documentos** (ex.: um aditivo prorrogou o contrato). A resposta mostra o valor original e o alterado. | Confira os dois documentos citados. |
| **Conflito** (vermelho) | Documentos **dizem coisas diferentes** (ex.: dois valores). O sistema **não escolhe** um deles. | Abra os documentos listados em "Conflito identificado" e verifique qual está correto. |
| **Informação ausente** (amarelo) | A informação **não foi encontrada** nos documentos. | Verifique se o documento está na pasta; reformule a pergunta. |
| **Trechos localizados** (cinza) | Não há resposta pronta, mas há trechos sobre o assunto. | Leia os trechos exibidos. |
| **Resposta redigida por IA (validada)** (azul) | Texto escrito pela inteligência artificial local, com números e datas conferidos nos documentos. | Confira as fontes numeradas [1], [2]… |

2. **Confiança** — alta, média ou baixa. Respostas que usam texto lido de documentos digitalizados (OCR) ficam, no
   máximo, com confiança **média**.
3. **Texto da resposta.**
4. **Quadros adicionais** (quando houver):
   - aviso cinza: por exemplo, *"Como a pergunta não informa o número do contrato, foi considerado o único contrato…"*;
   - aviso amarelo: por exemplo, *"Parte das fontes foi lida por OCR…; confira os valores no documento original."*;
   - **Conflito identificado**: lista cada documento com o valor divergente;
   - **Trechos dos documentos**: trechos transcritos para conferência.
5. **Fontes** — cada documento usado, com página e seção. Em cada fonte:
   - **Visualizar**: abre o documento em uma nova aba do navegador (PDFs abrem na página citada);
   - **Abrir no Windows**: abre o arquivo no programa padrão (Word, Excel…). Só aparece no computador onde o sistema
     está instalado;
   - etiqueta **OCR**: o texto foi reconhecido de um documento digitalizado.
6. **Quando a IA está ativada** — a etiqueta **IA local** aparece ao lado da confiança. Clique em **"Ver resposta do
   mecanismo local"** para comparar com a resposta produzida sem IA. Se a resposta da IA tiver sido descartada,
   aparece **"Ver resposta descartada da IA"**.
7. **Exportar resultado** — botões **PDF**, **DOCX**, **XLSX** e **JSON** para baixar a resposta como relatório.

**Erros e situações possíveis:**

| Mensagem | O que significa | Como resolver |
|---|---|---|
| Digite uma pergunta para pesquisar nos documentos. | A pergunta está vazia ou muito curta. | Escreva a pergunta completa. |
| Não localizei o Contrato nº X nos documentos disponibilizados. | Nenhum documento cita esse número. | Confira o número (formato `034/2022`). |
| Não localizei essa informação nos documentos disponibilizados. | O assunto não foi encontrado. | Reformule com outras palavras ou verifique se o documento está na pasta. |
| Foram localizados registros … em documentos de contratos diferentes … Informe o número do contrato… | Há vários contratos e a pergunta não disse qual. | Repita a pergunta com o número do contrato. |
| A resposta redigida pela IA foi descartada na validação (…). Exibida a resposta do mecanismo local. | A IA citou algo que não está nos documentos; o sistema descartou e mostrou a resposta segura. | Nada a fazer. Você pode ver o texto descartado em "Ver resposta descartada da IA". |
| IA indisponível (…). Exibida a resposta do mecanismo local. | A IA local não respondeu. | A resposta exibida continua válida. Avise um administrador. |

### 5.3 Consultar documentos

**Objetivo:** ver todos os documentos lidos pelo sistema, sua situação e seus detalhes.

**Quem pode usar:** todos. **Reindexar este documento** é só para administradores; **Abrir** só no computador do
sistema.

#### Procurar e filtrar

1. Na barra lateral, clique em **Documentos**.
2. Para procurar, digite no campo **Filtrar por nome, pasta ou nº do contrato** (a lista se atualiza sozinha).
3. Para filtrar pela situação, escolha uma opção em **Todos os status**.
4. Para filtrar pelo tipo, escolha uma opção em **Todos os tipos**.

> 📷 [CAPTURA DE TELA: tela Documentos com o campo de filtro, as listas "Todos os status" e "Todos os tipos" e a
> tabela com as colunas Documento, Tipo, Status, Contrato, Tamanho, Modificado e os botões Detalhes/Visualizar/Abrir]

**Colunas da tabela:** Documento (nome e pasta), Tipo (Contrato, Termo Aditivo, Certidão…), Status, Contrato
(número relacionado), Tamanho e Modificado (data de modificação do arquivo).

**Tipos de documento** (lista **Todos os tipos**). O tipo é deduzido pelo nome do arquivo e pelo título do documento:

| Tipo | Exemplos de documentos |
|---|---|
| Contrato | Termo de contrato |
| Termo Aditivo | 1º Termo Aditivo, aditivo de prorrogação (mostra a ordem, ex.: "(1º)") |
| Apostilamento | Apostila de reajuste |
| Portaria | Portaria de designação de fiscal |
| Notificação | Notificações à contratada |
| Certidão / Regularidade | Certidões negativas, FGTS (CRF), trabalhista (CNDT), INSS |
| Fatura / Nota Fiscal | Notas fiscais, faturas |
| Relatório | Relatórios de fiscalização |
| Edital | Edital da licitação |
| Termo de Referência | Termo de referência |
| Planilha | Planilhas de itens e custos |
| Outro | Qualquer documento não enquadrado acima |

> 💡 Dica: nomes de arquivo claros (ex.: `2_Termo_Aditivo_034_2022.pdf`, `Certidao_FGTS_Empresa.pdf`) ajudam o
> sistema a classificar corretamente.

**Significado de cada status:**

| Status | Significado | O que fazer |
|---|---|---|
| Documento com texto | Lido normalmente. | Nada. |
| Documento com OCR | Era digitalizado; o texto foi reconhecido automaticamente. | Confira valores importantes no original. |
| Documento escaneado | PDF digitalizado ainda sem texto reconhecido. | Peça a um administrador para ativar o OCR (seção 5.7). |
| Sem texto extraível | Imagem ou arquivo sem texto legível. | Idem; ou verifique a qualidade da digitalização. |
| Corrompido / protegido | Arquivo danificado ou com senha. | Abra o original; se tiver senha, salve uma cópia sem senha na pasta. |
| Formato não suportado | Tipo de arquivo que o sistema não lê. | Salve como PDF, DOCX ou XLSX, se for importante. |
| Removido do diretório | O arquivo foi apagado ou movido da pasta. | Nenhuma; o histórico é mantido. |

#### Ver os detalhes de um documento

1. Na linha do documento, clique em **Detalhes**.
2. Uma janela mostra caminho, tipo, status, contrato relacionado, páginas, trechos indexados, tamanho, datas, OCR,
   código de verificação (hash) e as seções identificadas.
3. Para fechar, clique em **✕**.

#### Abrir um documento

- **Visualizar**: abre no navegador (funciona de qualquer computador). Arquivos Word/Excel são baixados.
- **Abrir** / **Abrir no Windows**: abre no programa padrão do computador do sistema (só aparece nele).

#### Reindexar um documento (administradores)

Use quando um arquivo foi substituído e você não quer esperar a próxima atualização geral.

1. Clique em **Detalhes**.
2. Clique em **Reindexar este documento**.
3. Aparece *"Documento reindexado: (situação)."*

#### Verificar duplicidades

1. Clique em **Verificar duplicidades**.
2. Aparece o quadro **Duplicidades** com:
   - **Conteúdo idêntico**: arquivos exatamente iguais (cópias);
   - **Versões possivelmente relacionadas**: nomes parecidos (ex.: "Contrato_final" e "Contrato_v2").
3. Nenhum arquivo é apagado. A limpeza, se desejada, é feita manualmente na pasta pelos responsáveis.

#### Exportar a lista de documentos

1. Clique em **Exportar inventário (XLSX)**.
2. Uma planilha do Excel é baixada (pasta **Downloads** do seu computador).

| Mensagem | Significado | Como resolver |
|---|---|---|
| O arquivo original não está mais disponível no diretório documental. | O arquivo foi apagado ou movido. | Procure o arquivo; um administrador pode atualizar o índice. |
| Esta função só pode ser usada no computador onde o sistema está instalado. | Você clicou em "Abrir" pela rede. | Use **Visualizar**. |

### 5.4 Checklist

**Objetivo:** verificar, de uma vez, se os documentos exigidos em uma lista estão na pasta, válidos e corretos.

**Quem pode usar:** todos. Alterar e excluir um checklist: somente **quem o criou** ou um **administrador**.

#### Criar e executar um checklist

1. Na barra lateral, clique em **Checklist**.
2. Confira se a lista no alto à direita mostra **Novo checklist** (se não, selecione essa opção).
3. No campo **Nome**, digite um nome para identificar o checklist.
4. (Opcional) No campo **Contrato (opcional)**, digite o número do contrato.
5. No campo **Requisitos — um por linha**, digite ou cole a lista de documentos exigidos, **um em cada linha**.
6. Clique em **Salvar e executar**.
7. Aguarde: o botão mostra *"Executando…"* e, ao terminar, aparece *"Checklist avaliado."*

> 📷 [CAPTURA DE TELA: tela Checklist com os campos Nome, Contrato (opcional) e a caixa "Requisitos — um por linha"
> preenchida com uma lista numerada, e os botões "Carregar de arquivo…", "Salvar" e "Salvar e executar"]

| Campo | O que preencher | Obrigatório | Formato / regras | Exemplo |
|---|---|---|---|---|
| Nome | Identificação do checklist | Sim | Até 200 caracteres | `Prorrogação — Contrato 034/2022` |
| Contrato (opcional) | Número do contrato a conferir | Não | `NNN/AAAA` (aceita `34/2022`) | `034/2022` |
| Requisitos — um por linha | Documentos exigidos | Sim | Um requisito por linha; aceita numeração (`1.`, `1)`, `a)`, `ITEM 01`), marcadores (`-`, `•`, `[ ]`) | ver abaixo |

**Por que informar o contrato?** Com o número, o sistema procura **apenas** nos documentos desse contrato e nas
certidões com o CNPJ da contratada. Sem ele, procura em todos os documentos.

**Exemplo de requisitos:**

```text
DOCUMENTOS CONTRATUAIS
1. Contrato assinado (obrigatório)
2. Termo aditivo de prorrogação
3. Portaria de designação do fiscal
DOCUMENTOS DE REGULARIDADE
4. Certidão de regularidade do FGTS
5. Certidão negativa de débitos trabalhistas
6. Garantia contratual (se houver)
```

- Linhas em **MAIÚSCULAS** (ou terminadas com `:`) viram **grupos**, e não itens.
- *(obrigatório)* marca prioridade alta; *(se houver)* ou *(opcional)* marca prioridade baixa.
- Escreva requisitos claros, citando o documento ("Certidão de regularidade do FGTS" é melhor que "FGTS").

**Carregar a lista de um arquivo:**

1. Clique em **Carregar de arquivo…**.
2. Escolha o arquivo no seu computador (TXT, MD, CSV, DOC, DOCX, RTF, ODT, XLS, XLSX, ODS ou PDF, até 10 MB).
3. O texto aparece na caixa de requisitos, com a mensagem *"Arquivo carregado. Revise os itens e clique em Salvar."*
4. Revise e corrija a lista, se necessário.
5. Clique em **Salvar e executar**.

**Salvar sem executar:** clique em **Salvar**. Aparece *"Checklist salvo com N item(ns)."*

#### Entender o resultado

Abaixo do formulário aparece o resultado: um resumo por situação (botões arredondados), a lista de itens e a
organização virtual dos documentos.

> 📷 [CAPTURA DE TELA: resultado de um checklist com os botões de resumo (Todos, ATENDIDO, VENCIDO…), itens com
> etiquetas coloridas, justificativas, documentos de evidência com "Visualizar", e o quadro "Organização virtual dos
> documentos"]

Cada item mostra: número (ITEM 01…), descrição, prioridade, **situação**, confiança, **justificativa** (o porquê) e
as **evidências** (documento, página, trecho).

| Situação | O que significa | O que fazer |
|---|---|---|
| **ATENDIDO** | O documento exigido foi encontrado e passou nas verificações (assunto, assinatura, validade). | Nada; confira a evidência se for crítico. |
| **PARCIALMENTE ATENDIDO** | Só parte foi comprovada (ex.: certidão do FGTS sim, do INSS não). | Providencie o que falta (está na justificativa). |
| **AUSENTE** | O tipo de documento exigido não foi encontrado. | Providencie o documento e coloque-o na pasta. |
| **DÚVIDA** | Há indícios, mas não comprovação (ex.: documento digitalizado sem texto, aditivo que não trata do assunto pedido). | Confira manualmente o documento indicado. |
| **DUPLICADO** | O mesmo requisito foi escrito duas vezes na lista. | Remova a linha repetida, se quiser. |
| **VENCIDO** | A validade da certidão ou a vigência do contrato já terminou. | Providencie a versão atualizada. |
| **INCOMPATÍVEL** | Há documento do tipo, mas de outro contrato ou CNPJ. | Verifique se o documento correto está na pasta. |
| **NÃO IDENTIFICADO** | Não há nenhuma evidência (não significa que o documento não exista). | Verifique manualmente ou reescreva o requisito de forma mais clara. |

> ⚠️ ATENÇÃO: "Contrato assinado" fica **ATENDIDO com confiança média** quando o texto só mostra local e data da
> assinatura. O sistema não "vê" as assinaturas: confira no documento original.

**Filtrar por situação:** clique em um botão do resumo (ex.: **VENCIDO (2)**) ou escolha em **Todos os status**.

**Organização virtual dos documentos:** agrupa os documentos que comprovam os itens em "pastas" (01 — Contrato,
02 — Termos Aditivos…) e lista os **Itens sem documento** e os **Itens a conferir**. É só uma visualização: **nenhum
arquivo é copiado ou movido**.

#### Abrir, alterar ou excluir um checklist salvo

1. Na lista no alto à direita, escolha o checklist (aparecem nome, contrato, quantidade de itens e autor).
2. Para **alterar**: edite os campos e clique em **Salvar** ou **Salvar e executar**.
3. Para **excluir**: clique em **Excluir** e confirme. Os documentos **não** são afetados.

> Checklist criado por outra pessoa: aparece o aviso *"Checklist criado por … você pode executar e exportar, mas
> somente o autor ou um administrador pode alterá-lo ou excluí-lo."* e o botão passa a se chamar **Executar**.

#### Exportar o resultado

Ao lado de **Exportar:**, clique em **PDF**, **DOCX**, **XLSX**, **CSV**, **TXT** ou **JSON**. O arquivo vai para a pasta
**Downloads**.

**Erros possíveis:**

| Mensagem | Significado | Como resolver |
|---|---|---|
| Informe um nome para o checklist. | Campo Nome vazio. | Preencha o nome. |
| Nenhum item foi identificado. Informe um requisito por linha. | A caixa de requisitos está vazia ou só tem títulos. | Escreva os requisitos, um por linha. |
| Número de contrato inválido. Use o formato 034/2022. | O contrato foi digitado em formato errado. | Use `NNN/AAAA` ou deixe em branco. |
| Formato não suportado. Use TXT, MD, CSV, DOC, DOCX, RTF, ODT, XLS, XLSX, ODS ou PDF. | Arquivo de tipo não aceito. | Salve a lista em um desses formatos. |
| Arquivo muito grande (limite de 10 MB). | O arquivo da lista passa de 10 MB. | Copie e cole o texto da lista. |
| Não foi possível extrair o texto do arquivo. | Arquivo digitalizado, protegido ou danificado. | Copie e cole o texto da lista. |
| Somente quem criou este checklist ou um administrador pode alterá-lo ou excluí-lo. | O checklist é de outra pessoa. | Crie o seu próprio ou peça ao autor. |

### 5.5 Relatórios

**Objetivo:** gerar documentos para arquivo, envio ou impressão.

**Quem pode usar:** todos.

1. Na barra lateral, clique em **Relatórios**.
2. Escolha o cartão do relatório desejado.
3. Se o cartão pedir, preencha o campo (pergunta ou checklist).
4. Clique no formato: **PDF**, **DOCX**, **XLSX**, **CSV** ou **JSON**.
5. O arquivo é baixado e aparece *"Relatório gerado: nome-do-arquivo"*.

> 📷 [CAPTURA DE TELA: tela Relatórios com os seis cartões (Resultado da consulta, Inventário documental, Checklist,
> Documentos ausentes, Conflitos documentais, Contratos identificados), cada um com botões PDF/DOCX/XLSX/CSV/JSON, e a
> tabela "Relatórios gerados"]

| Relatório | Conteúdo | O que pede |
|---|---|---|
| Resultado da consulta | Resposta a uma pergunta, com conflitos, trechos e fontes. | Digitar a pergunta |
| Inventário documental | Todos os documentos, com tipo, situação e contrato. | — |
| Checklist | Itens, situações, evidências e organização virtual. | Escolher o checklist |
| Documentos ausentes | Itens ausentes, vencidos ou incompletos e arquivos que saíram da pasta. | Checklist (ou "Todos os checklists") |
| Conflitos documentais | Informações divergentes entre documentos de um mesmo contrato e alterações por aditivos. | — |
| Contratos identificados | Dados de cada contrato, situação após aditivos e itens contratados. | — |

**Qual formato escolher:**

| Formato | Para quê |
|---|---|
| PDF | Imprimir, anexar a processos, enviar. |
| DOCX | Editar no Word. |
| XLSX | Filtrar e ordenar no Excel. |
| CSV | Importar em outros sistemas. |
| JSON | Uso técnico (integração com outros sistemas). |

**Relatórios gerados:** a tabela no fim da tela lista os relatórios já gerados (por qualquer usuário). Clique em
**Baixar** para obter de novo.

| Mensagem | Significado | Como resolver |
|---|---|---|
| Informe a pergunta para gerar o relatório da consulta. | Campo da pergunta vazio. | Escreva a pergunta no cartão. |
| Selecione o checklist. | Nenhum checklist escolhido (ou nenhum cadastrado). | Crie um checklist antes (seção 5.4). |

### 5.6 Usuários (administradores)

**Objetivo:** controlar quem acessa o sistema.

**Quem pode usar:** somente administradores.

> 📷 [CAPTURA DE TELA: tela Usuários com o formulário "Novo usuário" (Usuário, Nome completo, Perfil, Senha temporária,
> botão "Criar usuário") e a tabela de usuários com as colunas Usuário, Nome, Perfil, Situação, Último acesso e os
> botões "Redefinir senha", "Desativar"]

#### Criar um usuário

1. Na barra lateral, clique em **Usuários**.
2. No quadro **Novo usuário**, preencha **Usuário**.
3. Preencha **Nome completo**.
4. Escolha o **Perfil**: **Consulta** ou **Administrador** (veja a seção 6).
5. Preencha **Senha temporária**.
6. Clique em **Criar usuário**.
7. Aparece *"Usuário X criado. Informe a senha temporária pessoalmente."*
8. Informe à pessoa o usuário e a senha temporária **pessoalmente** (nunca por e-mail ou grupo de mensagens).

| Campo | Regras | Exemplo |
|---|---|---|
| Usuário | 3 a 50 caracteres: minúsculas sem acento, números, `.`, `-`, `_` | `joao.lima` |
| Nome completo | Obrigatório, até 120 caracteres | `João Lima` |
| Perfil | Consulta ou Administrador | Consulta |
| Senha temporária | 8+ caracteres, letras e números, diferente do usuário | `Inicio2026` (apenas exemplo — não use) |

#### Alterar o perfil

1. Na linha do usuário, escolha o novo perfil na coluna **Perfil**.
2. Aparece *"Perfil alterado."*

#### Desativar ou reativar

1. Clique em **Desativar** e confirme. A pessoa é desconectada na hora e não consegue mais entrar.
2. Para devolver o acesso, clique em **Reativar**.

> Prefira **desativar** a excluir: o sistema mantém o histórico. (Não há botão de exclusão de usuários.)

#### Redefinir a senha (quando alguém esquece)

1. Clique em **Redefinir senha** na linha do usuário.
2. Na janela, digite uma **Senha temporária**.
3. Clique em **Redefinir**.
4. Informe a senha temporária à pessoa, pessoalmente. Ela terá de trocá-la no próximo acesso.

#### Desbloquear (após 5 senhas erradas)

1. A situação do usuário aparece como **Bloqueado**.
2. Clique em **Desbloquear**.

**Coluna Situação:** Ativo, Aguardando troca de senha, Bloqueado ou Desativado.

| Mensagem | Significado | Como resolver |
|---|---|---|
| Já existe um usuário "X". | Nome de usuário em uso. | Escolha outro (ex.: `joao.lima2`). |
| Não é possível remover o último administrador ativo. | Ficaria sem nenhum administrador. | Crie ou promova outro administrador antes. |
| Informe o nome completo. | Campo vazio. | Preencha o nome. |

### 5.7 Configurações (administradores)

**Objetivo:** ajustar o funcionamento do sistema.

**Quem pode usar:** somente administradores. "Selecionar pasta…" só aparece no computador do sistema.

> 📷 [CAPTURA DE TELA: tela Configurações mostrando os quadros Diretório documental, Indexação, Verificação do sistema,
> OCR — documentos digitalizados, Mecanismo de respostas (IA opcional), Sistema e Logs]

#### Diretório documental (a pasta dos documentos)

A pasta definida para os documentos desta instalação é:
`D:\AGENTES\INTELIGENCIA_DOCUMENTAL_GESTAO_ CONTRATO\DOCUMENTOS`
`[VERIFICAR: confirmar que a pasta foi criada e configurada após a instalação]`

1. Na barra lateral, clique em **Configurações**.
2. No quadro **Diretório documental**, digite o caminho da pasta, ou clique em **Selecionar pasta…** (só no
   computador do sistema) e escolha a pasta na janela do Windows.
3. Clique em **Salvar**.
4. Aparece *"Diretório documental salvo. Inicie a indexação para atualizar o índice."*
5. No quadro **Indexação**, clique em **Iniciar indexação**.

> Para **incluir documentos** no sistema, basta **copiá-los para a pasta** (pode ter subpastas) e clicar em
> **Atualizar índice** no Painel. Para **retirar**, remova-os da pasta e atualize o índice.

| Mensagem | Significado | Como resolver |
|---|---|---|
| O diretório X não existe. | Caminho digitado errado ou pasta inexistente. | Confira o caminho (copie da barra de endereço do Explorador de Arquivos). |
| Sem permissão de leitura em X. | O sistema não consegue ler a pasta. | Procure a TI. |
| Não foi possível abrir o seletor de pastas. Digite o caminho manualmente. | A janela de seleção não abriu. | Digite o caminho. |

#### Indexação

- **Iniciar indexação**: lê apenas os arquivos **novos ou alterados** (rápido).
- **Reindexar tudo**: lê **todos** os arquivos de novo (demorado; use após mudanças de configuração). Pede
  confirmação.

#### Verificação do sistema

1. Clique em **Verificar sistema**.
2. Aparece uma lista com **OK** (verde), **WARNING** (amarelo, atenção) ou **ERRO** (vermelho).
3. Se houver ERRO, avise a TI (veja o Manual Técnico).

#### OCR — documentos digitalizados

O **OCR** "lê" o texto de documentos escaneados e fotos.

1. Marque **Ativar OCR**.
2. Em mecanismo, deixe **Automático (Windows, depois Tesseract)**. As outras opções são **OCR do Windows** (o
   recurso já existente no Windows) e **Tesseract OCR** (programa opcional, só se a TI o tiver instalado). Abaixo,
   a lista mostra cada mecanismo como **DISPONÍVEL** ou **INDISPONÍVEL** e qual está **EM USO**.
3. Clique em **Salvar**.
4. Clique em **Testar OCR**: deve aparecer **[OK]** e *"6 de 6 palavras de controle reconhecidas"* (ou 5 de 6).
5. Clique em **Reprocessar digitalizados** para ler os documentos escaneados já existentes.

#### Mecanismo de respostas (IA opcional)

Permite que uma inteligência artificial **instalada no próprio computador** escreva as respostas. A instalação é feita
pela TI (Manual Técnico). Depois de instalada:

1. Em **Mecanismo**, escolha **LLM local (Ollama / LM Studio)**.
2. Em **Endereço do servidor**, mantenha `http://127.0.0.1:11434/v1`.
3. Clique em **Listar modelos**.
4. Em **Modelo**, escolha o modelo instalado.
5. Clique em **Salvar**.
6. Clique em **Testar conexão**: deve aparecer *"IA respondeu em …"*.

Para voltar ao funcionamento sem IA, escolha **Local — somente documentos (sem IA)** e clique em **Salvar**.

#### Sistema e Logs

- **Sistema**: mostra o endereço do painel e se a indexação automática está ligada.
- **Logs**: **Carregar últimos registros** mostra o histórico técnico (útil para a TI).

---

## 6. Perfis e permissões

| Ação | Consulta | Administrador |
|---|:---:|:---:|
| Entrar, alterar a própria senha, sair | ✅ | ✅ |
| Ver o Painel | ✅ | ✅ |
| Atualizar índice / Reindexar documento | ❌ | ✅ |
| Fazer perguntas e exportar respostas | ✅ | ✅ |
| Ver, filtrar e visualizar documentos | ✅ | ✅ |
| Abrir documento no Windows (somente no computador do sistema) | ✅ | ✅ |
| Verificar duplicidades e exportar inventário | ✅ | ✅ |
| Criar, executar e exportar checklists | ✅ | ✅ |
| Alterar e excluir checklists **próprios** | ✅ | ✅ |
| Alterar e excluir checklists **de outras pessoas** | ❌ | ✅ |
| Gerar e baixar relatórios | ✅ | ✅ |
| Gerenciar usuários | ❌ | ✅ |
| Configurações (pasta, indexação, OCR, IA, logs, verificação) | ❌ | ✅ |

> **Não se aplica:** não há outros perfis nem permissões por contrato ou por pasta: todos os usuários conectados veem
> todos os documentos indexados.

---

## 7. Perguntas frequentes

**O sistema altera ou apaga meus documentos?**
Não. Ele apenas **lê** os arquivos. Nenhum documento é movido, renomeado, alterado ou apagado.

**Os documentos são enviados para a Internet?**
Não. Tudo é processado no computador da instituição. A IA opcional também roda no próprio computador.

**Por que a resposta diz "Não localizei essa informação" se eu sei que ela existe?**
Possíveis motivos: o documento não está na pasta; é digitalizado e o OCR está desligado; o texto usa palavras
diferentes; ou o índice não foi atualizado. Tente reformular, inclua o número do contrato e peça a um administrador
para atualizar o índice.

**Coloquei um documento novo na pasta e ele não aparece.**
O índice precisa ser atualizado: um administrador clica em **Atualizar índice** no Painel. Ao iniciar o sistema, a
atualização também é feita automaticamente.

**O que é "Inferência documental"?**
É quando a resposta depende da relação entre documentos, por exemplo: o contrato terminava em 2023, mas um aditivo
prorrogou para 2024. O sistema mostra os dois e avisa.

**O que fazer quando aparece "Conflito"?**
Abrir os documentos listados e verificar qual informação é a correta. O sistema nunca escolhe sozinho.

**Posso usar o sistema pelo celular?**
`[VERIFICAR: depende da liberação do acesso pela rede/Wi-Fi institucional pela TI]` A tela se adapta a telas
pequenas, mas o uso recomendado é em computador.

**Esqueci a senha. Recebo por e-mail?**
Não. Um administrador redefine a senha (seção 3.5).

**Quanto tempo fico conectado?**
Até 8 horas, ou até clicar em **Sair**.

**Posso ver checklists de outras pessoas?**
Sim, e também executá-los e exportá-los. Alterar ou excluir, somente o autor ou um administrador.

**Onde ficam os arquivos que eu exporto?**
Na pasta **Downloads** do seu computador (ou onde o navegador estiver configurado para salvar).

---

## 8. Resolução de problemas comuns

### "A página não carrega" / "Não é possível acessar esse site"

1. Confira o endereço digitado (seção 2), letra por letra.
2. Se estiver em **outro computador**, tente abrir de novo após 1 minuto.
3. Pergunte a um colega se para ele funciona:
   - se **para ninguém** funciona: o computador do sistema pode estar desligado ou o sistema parado. Avise o
     administrador ou a TI;
   - se **só para você** não funciona: avise a TI e informe que pode ser o **proxy** do navegador ou o computador fora da lista
     de computadores autorizados.

### "Não consigo entrar"

| O que aparece | O que fazer |
|---|---|
| Usuário ou senha inválidos. | Verifique se o **Caps Lock** está desligado (a luz no teclado). Digite o usuário em minúsculas. Tente de novo com calma: 5 erros bloqueiam a conta. |
| Conta bloqueada temporariamente… | Aguarde 15 minutos ou peça desbloqueio a um administrador. |
| Usuário desativado. | Procure um administrador. |
| Este computador não está autorizado a acessar o sistema. | Procure a TI. |
| Sistema ainda não configurado | O primeiro administrador ainda não foi criado (seção 3.1). |

### "Fui desconectado no meio do trabalho"

A sessão dura 8 horas, ou foi encerrada porque um administrador redefiniu sua senha ou desativou seu usuário. Entre
novamente. Respostas e checklists já salvos não se perdem.

### "O botão não faz nada"

1. Aguarde alguns segundos: alguns processos (checklist, OCR, IA) demoram.
2. Veja se apareceu uma mensagem vermelha no canto inferior direito.
3. Recarregue a página com a tecla **F5**.
4. Se continuar, entre novamente (**Sair** e **Entrar**).
5. Persistindo, avise a TI informando o que tentou fazer e a mensagem exibida.

### "Não vejo o menu Configurações / Usuários / o botão Atualizar índice"

São funções de **administrador**. Se você precisa delas, peça a um administrador.

### "O botão Abrir no Windows não aparece"

Ele só aparece no computador onde o sistema está instalado. Use **Visualizar**.

### "Visualizar baixa o arquivo em vez de mostrar"

É o comportamento normal para Word, Excel e PowerPoint: o arquivo vai para **Downloads**. PDFs abrem no navegador.

### "A resposta está estranha ou incompleta"

1. Inclua o número do contrato na pergunta.
2. Use palavras que aparecem nos documentos (ex.: "vigência", "valor global").
3. Confira as **Fontes**: o sistema mostra exatamente de onde tirou a informação.
4. Se um documento digitalizado for a fonte (etiqueta **OCR**), confira no original.

### "O download não começa"

Verifique se o navegador bloqueou o download (ícone na barra de endereços ou na barra inferior) e permita.

---

## 9. Glossário

| Termo | Significado |
|---|---|
| **Administrador** | Usuário com permissão total: cadastra usuários e configura o sistema. |
| **Aditivo (termo aditivo)** | Documento que altera um contrato (prazo, valor, itens). |
| **Barra de endereços** | Faixa no alto do navegador onde se digita o endereço da página. |
| **Caps Lock** | Tecla que deixa todas as letras maiúsculas; com ela ligada, a senha sai errada. |
| **Checklist** | Lista de documentos ou requisitos que precisam ser comprovados. |
| **CNPJ** | Número de identificação de empresas (formato 00.000.000/0000-00). |
| **Confiança** | Grau de segurança da resposta: alta, média ou baixa. |
| **Conflito** | Situação em que documentos informam valores diferentes para a mesma coisa. |
| **Consulta (perfil)** | Usuário que usa o sistema, mas não o configura. |
| **CSV** | Tipo de arquivo de tabela simples, que abre no Excel. |
| **Diretório documental** | A pasta do computador onde ficam os documentos que o sistema lê. |
| **DOCX** | Arquivo do Microsoft Word. |
| **Downloads** | Pasta do computador onde os arquivos baixados são salvos. |
| **Evidência** | Trecho de documento que comprova um item do checklist. |
| **Fonte** | Documento (e página) de onde a informação foi tirada. |
| **Hash** | "Impressão digital" de um arquivo: um código que muda se o arquivo mudar. |
| **IA (inteligência artificial)** | Programa que redige textos; aqui é opcional e roda no próprio computador. |
| **Indexar / índice** | Ler os documentos e organizar o conteúdo para que as buscas sejam rápidas. |
| **Inferência** | Conclusão tirada da relação entre documentos. |
| **JSON** | Formato de arquivo técnico, usado para integração entre sistemas. |
| **Login** | Ato de entrar no sistema com usuário e senha. |
| **Navegador** | Programa para abrir páginas (Edge, Chrome, Firefox). |
| **OCR** | Reconhecimento de texto em imagens e documentos escaneados. |
| **PDF** | Formato de documento para leitura e impressão. |
| **Perfil** | Tipo de usuário (Administrador ou Consulta), que define o que ele pode fazer. |
| **Proxy** | Equipamento da rede que intermedeia o acesso dos navegadores; pode bloquear endereços internos. |
| **Reindexar** | Ler novamente um ou todos os documentos. |
| **Senha temporária** | Senha provisória dada pelo administrador, que deve ser trocada no primeiro acesso. |
| **Sessão** | O período em que você permanece conectado após entrar. |
| **Vigência** | Período em que o contrato vale (do início ao término). |
| **XLSX** | Arquivo do Microsoft Excel. |
