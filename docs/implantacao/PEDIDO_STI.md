# Pedido à STI — publicação do SAD-GD na rede interna

**Sistema:** SAD-GD (apoio à decisão e gestão documental), servidor em uma estação da SEMA, acesso apenas pela rede
interna, com login e auditoria. Nenhum dado é enviado a serviços externos (LLM, busca e transcrição de voz locais).

| # | Item | Detalhe |
|---|---|---|
| 1 | **IP fixo** para a estação | IP atual da placa Ethernet (informado à STI fora do repositório). Reserva DHCP ou IP estático |
| 2 | **Registro DNS interno** | `sad.sema.mt.gov.br` tipo A → IP do item 1 |
| 3 | **Certificado TLS** do nome | Para `sad.sema.mt.gov.br` (ou curinga `*.sema.mt.gov.br`), confiável nos navegadores da SEMA (autoridade interna distribuída por GPO ou certificado público). Formato **.pfx com senha** (ou .crt + .key + cadeia). Validade mínima de 1 ano |
| 4 | **Liberação de rede** | Entrada TCP **443** na estação a partir das redes internas. O firewall do Windows da estação é configurado pelo script do sistema (somente faixas privadas) |
| 5 | Política de energia (se gerida por GPO) | A estação não deve suspender/hibernar no horário de uso |

**Contato técnico / instalação:** com o certificado em mãos, a instalação leva poucos minutos
(`scripts\rede\instalar_certificado.py` valida nome, validade e chave antes de usar; `scripts\rede\publicar_rede.ps1`
configura servidor, firewall e início automático). A chave privada fica restrita ao usuário da estação, fora do
repositório de código.
