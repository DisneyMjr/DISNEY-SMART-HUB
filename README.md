# DISNEY-SMART-HUB

Central de aplicativos com visual escuro para instalar e abrir os seis programas Smart a partir do GitHub Releases.

## Identidade visual

O executável Windows utiliza `favicon.ico` como ícone, e a janela do launcher utiliza `favicon.png`. O arquivo fornecido tem resolução 64x64, adequada para uso básico, mas uma versão 256x256 melhora a nitidez em tamanhos grandes. No Linux o executável usa `favicon.png`.

## Instagram

O launcher possui um botão **Siga @disneymkt no Instagram** no topo e na página inicial. O botão abre https://instagram.com/disneymkt no navegador. Não exige login no Instagram para usar os aplicativos.

## Aplicativos

- VectorSmart
- FotoSmart
- Light Smart
- Video Maker
- Design Smart
- Effect Smart

Os endereços de origem podem ser alterados em `apps.json`. Confira especialmente o repositório do FotoSmart.

## Como funciona

1. Abra o DISNEY-SMART-HUB.
2. Escolha um aplicativo e clique em **Instalar**.
3. O DISNEY-SMART-HUB consulta a **última Release pública** do GitHub e procura um instalador compatível.
4. No Windows baixa o **MSI** e solicita autorização antes de abri-lo. O instalador conduz as etapas restantes. No Linux baixa a **AppImage**, guarda na pasta do usuário e habilita sua execução.
5. Use **Abrir** quando o DISNEY-SMART-HUB reconhecer a localização do executável.
6. **Verificar versão** compara visualmente a versão da Release com a versão registrada no Hub (quando disponível). Ele não realiza atualização silenciosa.

**Atenção**: um arquivo apenas em GitHub Actions > Artifacts não fica disponível para este launcher. É necessário publicar os instaladores em uma Release pública, com a arquitetura correta.

## Windows, Linux e versões

No Windows o programa baixa MSI x64 e abre o instalador interativo, sem elevar privilégios automaticamente. O Hub tenta reconhecer as pastas de instalação mais comuns; quando o aplicativo não estiver em uma dessas pastas ele pode continuar aparecendo como não instalado. No Linux usa AppImage x64 (não instala DEB/RPM). Uma AppImage instalada pelo Hub é armazenada na pasta de dados do usuário. O armazenamento de versão local ocorre no Linux; no Windows só a execução do MSI não confirma a instalação concluída.

Nenhuma validação de assinatura digital é realizada automaticamente neste protótipo. Para distribuição pública, assine os binários e publique hashes SHA-256 nos Releases; nunca ofereça instaladores de repos desconhecidos.

## Executar pelo código fonte

Instale Python 3.12+ e execute:

```shell
python -m pip install -r requirements.txt
python main.py
```

## Criar executáveis no GitHub

Publique estes arquivos em um repositório **DISNEY-SMART-HUB**. Depois acesse **Actions > Gerar DISNEY-SMART-HUB Windows e Linux > Run workflow**. Baixe os arquivos na seção **Artifacts**:

- `DisneySmartHub-Windows-x64`: executável portátil `DisneySmartHub.exe`, **não um MSI**.
- `DisneySmartHub-Linux-x64`: arquivo `DisneySmartHub-Linux-x64.tar.gz` com o executável portátil Linux.

Se quiser um MSI do próprio launcher, será necessário acrescentar um projeto WiX ou outro empacotador. Esta versão gera executáveis portáteis do Hub e instala **os aplicativos** a partir de MSIs publicados.

## Segurança e limites

- O aplicativo só procura a versão mais recente de cada repositório declarado em `apps.json`.
- O usuário precisa confirmar a abertura de instaladores MSI.
- O código de atualização não é executado automaticamente e não verifica assinatura digital.
- Os aplicativos precisam ter instaladores Linux e Windows já publicados como assets de uma GitHub Release.
- Se uma Release for privada, estiver ausente ou não contiver asset apropriado, o Hub mostra uma mensagem e não instala.


## Instalação pelo GitHub Releases

O hub consulta `https://api.github.com/repos/OWNER/REPO/releases/latest`.
O instalador **não usa** os Artifacts do Actions. Publique um arquivo `.msi` para Windows e `.AppImage` para Linux na última Release pública, e certifique-se de que `apps.json` aponta ao repositório certo.

A versão 0.4 corrige o ciclo das tarefas em segundo plano e exibe erros de rede, ausência de Release e ausência de instalador ao usuário.

## Atualização v0.5: diálogos e downloads

- Mensagens próprias em tema escuro, com texto selecionável e contraste alto.
- Confirmação de instalação do MSI com botões **Abrir instalador**, **Cancelar** e **Abrir pasta**.
- Barra de download com porcentagem quando o servidor informa o tamanho do arquivo.
- Verificação do tamanho do arquivo baixado antes de disponibilizá-lo.
- Botão **Instalar / atualizar** também para aplicativos já detectados.
- Verificação de Releases e comparação de versões quando o aplicativo tem uma versão instalada registrada.
- Os MSI são abertos com `msiexec /i`, com confirmação do usuário, e não são instalados silenciosamente.
- No Linux, o launcher baixa AppImage e a coloca na pasta do usuário.

**Importante:** O instalador MSI concluído não significa que o app foi instalado com êxito. A detecção só confirma a presença de um executável conhecido; a versão exata pode não ser detectável. O funcionamento depende de Releases com os instaladores apropriados publicados nos repositórios configurados.
