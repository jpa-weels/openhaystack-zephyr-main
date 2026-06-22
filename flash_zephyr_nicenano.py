#!/usr/bin/env python3
"""
Injeta a chave publica no firmware Zephyr OpenHaystack e gera UF2 para Nice Nano.
Uso: python flash_zephyr_nicenano.py <public_key_base64>
"""
import sys, struct, os, shutil
from base64 import b64decode

NRF52840_FAMILY_ID = 0xADA52840
UF2_MAGIC_START0   = 0x0A324655
UF2_MAGIC_START1   = 0x9E5D5157
UF2_MAGIC_END      = 0x0AB16F30
BLOCK_SIZE         = 256
APP_START          = 0x26000       # S140 v6.x - Nice Nano

PLACEHOLDER        = b'OFFLINEFINDINGPUBLICKEYHERE!'  # 28 bytes

def bin_to_uf2(data, base_addr, output_path):
    blocks = []
    addr = base_addr
    for i in range(0, len(data), BLOCK_SIZE):
        chunk = data[i:i+BLOCK_SIZE].ljust(BLOCK_SIZE, b'\xff')
        blocks.append((addr + i, chunk))

    total = len(blocks)
    with open(output_path, 'wb') as f:
        for idx, (addr, chunk) in enumerate(blocks):
            header = struct.pack('<IIIIIIII',
                UF2_MAGIC_START0, UF2_MAGIC_START1,
                0x00002000,       # flags: familyID presente
                addr, BLOCK_SIZE, idx, total,
                NRF52840_FAMILY_ID,
            )
            f.write(header + chunk.ljust(476, b'\x00') + struct.pack('<I', UF2_MAGIC_END))
    print(f"[*] UF2 gerado: {output_path} ({total} blocos, base=0x{base_addr:08X})")

def main():
    if len(sys.argv) < 2:
        print("Uso: python flash_zephyr_nicenano.py <public_key_base64>")
        print("Exemplo com a chave do minhas_chaves.txt:")
        print("  python flash_zephyr_nicenano.py BI1cavMUbq+...")
        sys.exit(1)

    # Decodifica chave publica (57 bytes) e extrai coordenada x (28 bytes)
    pub_full = b64decode(sys.argv[1])
    if len(pub_full) == 57:
        pub_key = pub_full[1:29]   # remove 0x04 prefix, pega so x
    elif len(pub_full) == 28:
        pub_key = pub_full
    else:
        print(f"[!] Chave invalida: {len(pub_full)} bytes (esperado 57 ou 28)")
        sys.exit(1)

    print(f"[*] Chave (28 bytes): {pub_key.hex()}")

    # Localiza zephyr.bin
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidatos = [
        os.path.join(script_dir, "zephyr.bin"),
        os.path.join(script_dir, "build", "zephyr", "zephyr.bin"),
    ]
    bin_path = next((c for c in candidatos if os.path.exists(c)), None)
    if not bin_path:
        print("[!] Arquivo zephyr.bin nao encontrado.")
        print("    Coloque o zephyr.bin na mesma pasta deste script.")
        sys.exit(1)

    print(f"[*] Lendo: {bin_path}")
    data = bytearray(open(bin_path, 'rb').read())

    # Injeta chave
    idx = data.find(PLACEHOLDER)
    if idx == -1:
        print("[!] Placeholder 'OFFLINEFINDINGPUBLICKEYHERE!' nao encontrado no binario!")
        print("    Verifique se o zephyr.bin e do projeto openhaystack-zephyr.")
        sys.exit(1)

    print(f"[*] Placeholder encontrado em offset 0x{idx:08X}, injetando chave...")
    data[idx:idx+28] = pub_key

    # Salva bin patchado
    patched_path = os.path.join(script_dir, "zephyr_patched.bin")
    open(patched_path, 'wb').write(data)
    print(f"[*] Binario patchado: {patched_path}")

    # Gera UF2 (bin comeca em APP_START para Nice Nano)
    uf2_path = os.path.join(script_dir, "openhaystack_zephyr.uf2")
    bin_to_uf2(bytes(data), APP_START, uf2_path)

    # Tenta copiar automaticamente para a placa
    print("\n[*] Procurando Nice Nano em modo bootloader...")
    for drive in "DEFGHIJKLMNOPQRSTUVWXYZ":
        info = f"{drive}:\\INFO_UF2.TXT"
        if os.path.exists(info):
            try:
                content = open(info).read()
                if "nrf" in content.lower() or "nice" in content.lower():
                    dest = f"{drive}:\\firmware.uf2"
                    print(f"[*] Placa encontrada em {drive}:\\, copiando...")
                    shutil.copy2(uf2_path, dest)
                    print("[*] Firmware copiado! A placa vai reiniciar.")
                    return
            except Exception:
                pass

    print("\n[!] Placa nao encontrada automaticamente.")
    print("=" * 55)
    print("GRAVE MANUALMENTE:")
    print("1. Clique 2x rapido no RESET -> aparece unidade NICENANO")
    print(f"2. Arraste para la: {uf2_path}")
    print("=" * 55)

if __name__ == "__main__":
    main()
