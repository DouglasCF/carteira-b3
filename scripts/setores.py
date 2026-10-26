"""Setor de ações, BDRs e ETFs e tipo de FII, para os insights de concentração do dashboard.

Lista genérica de ativos conhecidos da B3 (não é a carteira de ninguém). O que faltar ou estiver
diferente da sua leitura vai em dados/setores.json, que tem prioridade:
    {"TICKER": "Setor"}
Direitos de subscrição (XXXX12 a XXXX15) herdam o setor do XXXX11.
"""
import json
import re

from config import SETORES_USUARIO

_LISTA = {
    # ---------------------------------------------------------------- ações
    "Bancos": "ITUB3 ITUB4 ITSA3 ITSA4 BBDC3 BBDC4 BBAS3 SANB3 SANB4 SANB11 BPAC3 BPAC5 BPAC11 ABCB4 BRSR6 BMGB4 BPAN4 PINE4 BEES3 BAZA3 BMEB4 BRBI11"
              " ROXO34 INBR32 JPMC34 BOAC34 GSGI34 CTGP34 WFCO34 HSBC34 BCSA34",
    "Seguros": "BBSE3 PSSA3 CXSE3 IRBR3 SULA11 WIZC3",
    "Serviços financeiros": "B3SA3 CIEL3 XPBR31 STOC34 PAGS34 VISA34 MSCD34 PYPL34 AXPB34",
    "Holding diversificada": "BERK34",
    "Energia elétrica": "EGIE3 TAEE3 TAEE4 TAEE11 ELET3 ELET5 ELET6 CMIG3 CMIG4 CPLE3 CPLE5 CPLE6 CPFE3 EQTL3 ENGI3 ENGI4 ENGI11 TRPL4 ISAE4 ALUP11"
                        " AURE3 NEOE3 LIGT3 ENEV3 COCE5 CLSC4 MEGA3 SRNA3",
    "Saneamento": "SAPR3 SAPR4 SAPR11 SBSP3 CSMG3 ORVR3 AMBP3",
    "Petróleo e gás": "PETR3 PETR4 PRIO3 RECV3 BRAV3 RRRP3 UGPA3 VBBR3 RAIZ4 CSAN3 EXXO34 CHVX34",
    "Mineração e metais": "VALE3 CMIN3 BRAP3 BRAP4 CBAV3 AURA33 BCPX39 BSLV39 GOLD11",
    "Siderurgia": "GGBR3 GGBR4 GOAU4 CSNA3 USIM3 USIM5",
    "Papel e celulose": "SUZB3 KLBN3 KLBN4 KLBN11 RANI3",
    "Química": "UNIP6 BRKM5",
    "Agronegócio": "SOJA3 SLCE3 AGRO3 TTEN3 SMTO3 JALL3 LAND3",
    "Alimentos e bebidas": "ABEV3 BRFS3 MRFG3 MBRF3 BEEF3 MDIA3 CAML3 JBSS3 JBSS32 COCA34 PEPB34",
    "Bens industriais": "WEGE3 EMBR3 RAPT4 TUPY3 POMO4 KEPL3 MYPK3 FRAS3 LEVE3 SHUL4 ROMI3 DXCO3",
    "Saúde": "FLRY3 RDOR3 HAPV3 QUAL3 ODPV3 HYPE3 RADL3 PNVL3 DASA3 MATD3 BLAU3 ONCO3 VVEO3"
             " MRCK34 PFIZ34 JNJB34 ABBV34 LILY34 UNHH34",
    "Varejo": "MGLU3 LREN3 AZZA3 ARZZ3 BHIA3 AMER3 PETZ3 CEAB3 GUAR3 ASAI3 CRFB3 PCAR3 GMAT3 SBFG3 MLAS3 ALLD3 LJQQ3 VIVA3 MELI34 WALM34 COWC34",
    "Consumo": "GRND3 ALPA4 NTCO3 VULC3 CAMB3 PGCO34 MCDC34 SBUB34 NIKE34",
    "Imobiliário": "EVEN3 CYRE3 MRVE3 EZTC3 DIRR3 TEND3 CURY3 JHSF3 MULT3 IGTI11 ALOS3 ALSO3 LOGG3 HBRE3 LAVV3 PLPL3 MDNE3 TRIS3 GFSA3 HBOR3 MELK3 SYNE3",
    "Telecom": "VIVT3 TIMS3 OIBR3 DESK3 FIQE3 BRST3",
    "Tecnologia (big techs)": "AAPL34 MSFT34 GOGL34 GOGL35 AMZO34 M1TA34 NVDC34 TSLA34",
    "Tecnologia": "TOTS3 LWSA3 POSI3 INTB3 CASH3 BMOB3 NGRD3 IFCM3 ORCL34 CSCO34 IBMB34 ITLC34 ADBE34 SSFO34 A1MD34 TSMC34 ASML34 AVGO34 QCOM34 P2LT34 U1BE34 BABA34",
    "Aeroespacial e defesa": "SPCX34 BOEI34 LMTB34",
    "Mídia e entretenimento": "DISB34 NFLX34",
    "Turismo e viagens": "AIRB34 BOOK34",
    "Transporte e logística": "RAIL3 CCRO3 MOTV3 ECOR3 STBP3 AZUL4 GOLL4 RENT3 MOVI3 VAMO3 SIMH3 TGMA3 LOGN3 PORT3 JSLG3",
    "Educação": "COGN3 YDUQ3 SEER3 ANIM3 CSED3",
    # ---------------------------------------------------------------- ETFs
    "Índice amplo (Brasil)": "BOVA11 BOVV11 BOVX11 SMAL11 DIVO11 XBOV11",
    "Índice amplo (EUA)": "IVVB11 SPXI11 GPUS11 NASD11 BIVB39 BQQQ39",
    "Índice amplo (global)": "WRLD11 ACWI11 URTH11",
    "Índice amplo (emergentes)": "BEMV39 EMEG11",
    "Índice amplo (China)": "XINA11",
    "Índice amplo (Europa)": "EURP11",
    "Cripto": "HASH11 BITH11 QBTC11 ETHE11 QETH11",
    "Renda fixa": "IMAB11 B5P211 IRFM11 FIXA11 LFTS11 LFTB11 GPCA11 GPOS11 IB5M11 NTNS11",
    # ---------------------------------------------------------------- FIIs (tipo)
    "FII Logística": "HGLG11 XPLG11 BTLG11 VILG11 LVBI11 BRCO11 GGRC11 HSLG11 PATL11 RBRL11 SDIL11 GALG11 TRBL11 XPIN11 LGCP11 BLMG11",
    "FII Shoppings": "XPML11 VISC11 HGBS11 MALL11 HSML11 ABCP11 FIGS11",
    "FII Lajes corporativas": "HGRE11 BRCR11 JSRE11 RCRB11 PVBI11 VINO11 RBRP11 XPPR11 TEPP11 HGPO11",
    "FII Renda urbana": "TRXF11 HGRU11 ALZR11 RBVA11 GARE11 VIUR11",
    "FII Recebíveis (papel)": "KNCR11 KNIP11 KNSC11 KNHY11 MXRF11 RECR11 IRDM11 CPTS11 HGCR11 RBRR11 VGIR11 VRTA11 MCCI11 CVBI11 BCRI11 DEVA11"
                              " HABT11 RBRY11 VGIP11 XPCI11 URPR11 VCJR11 RZAK11 PORD11 OUJP11 SNCI11 AFHI11",
    "FII Fundo de fundos": "RBRF11 KFOF11 HFOF11 MGFF11 XPSF11 ITIP11 OUFF11 SNFF11 CPFF11 BCFF11",
    "FII Híbrido": "BTHF11 VGHF11 KNRI11 TGAR11",
    "Fiagro": "KNCA11 RZAG11 SNAG11 VGIA11 XPCA11 RURA11 BBGO11 AAZQ11 FGAA11",
    "FII Hotéis e saúde": "HCRI11 NSLU11 HTMX11",
}
SETORES = {t: s for s, ts in _LISTA.items() for t in ts.split()}
DIREITO = re.compile(r"^([A-Z]{4})1[2-5]$")


def mapa():
    """Setores genéricos + dados/setores.json do usuário (que tem prioridade)."""
    out = dict(SETORES)
    if SETORES_USUARIO.exists():
        out.update(json.loads(SETORES_USUARIO.read_text()))
    return out


def setor(ticker, m):
    if ticker in m:
        return m[ticker]
    d = DIREITO.match(ticker)
    return m.get(f"{d.group(1)}11") if d else None
