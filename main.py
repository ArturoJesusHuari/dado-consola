import ctypes
import math
import os
import secrets
import sys
import time


RESET = "\033[0m"
DIM = "\033[2m"

ANCHO = 61
ALTO = 27
ANGULO_VISTA = (math.atan(1 / 2), math.pi / 6, 0)

PUNTOS = {
    1: [(0, 0)],
    2: [(-0.5, -0.5), (0.5, 0.5)],
    3: [(-0.5, -0.5), (0, 0), (0.5, 0.5)],
    4: [(-0.5, -0.5), (0.5, -0.5), (-0.5, 0.5), (0.5, 0.5)],
    5: [(-0.5, -0.5), (0.5, -0.5), (0, 0), (-0.5, 0.5), (0.5, 0.5)],
    6: [
        (-0.5, -0.58), (0.5, -0.58),
        (-0.5, 0), (0.5, 0),
        (-0.5, 0.58), (0.5, 0.58),
    ],
}

# Cada cara contiene su normal y dos ejes locales para colocar los puntos.
CARAS = {
    "frente": ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
    "atras": ((0, 0, -1), (-1, 0, 0), (0, 1, 0)),
    "derecha": ((1, 0, 0), (0, 0, -1), (0, 1, 0)),
    "izquierda": ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
    "arriba": ((0, 1, 0), (1, 0, 0), (0, 0, -1)),
    "abajo": ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
}

VALORES_CARAS = {
    1: {"frente": 1, "atras": 6, "derecha": 3, "izquierda": 4, "arriba": 2, "abajo": 5},
    2: {"frente": 2, "atras": 5, "derecha": 3, "izquierda": 4, "arriba": 6, "abajo": 1},
    3: {"frente": 3, "atras": 4, "derecha": 6, "izquierda": 1, "arriba": 2, "abajo": 5},
    4: {"frente": 4, "atras": 3, "derecha": 1, "izquierda": 6, "arriba": 2, "abajo": 5},
    5: {"frente": 5, "atras": 2, "derecha": 3, "izquierda": 4, "arriba": 1, "abajo": 6},
    6: {"frente": 6, "atras": 1, "derecha": 4, "izquierda": 3, "arriba": 2, "abajo": 5},
}


def habilitar_colores():
    if os.name != "nt":
        return
    try:
        salida = ctypes.windll.kernel32.GetStdHandle(-11)
        modo = ctypes.c_uint()
        if ctypes.windll.kernel32.GetConsoleMode(salida, ctypes.byref(modo)):
            ctypes.windll.kernel32.SetConsoleMode(salida, modo.value | 0x0004)
    except (AttributeError, OSError):
        pass


def rotar(punto, ax, ay, az):
    x, y, z = punto
    cx, sx = math.cos(ax), math.sin(ax)
    y, z = y * cx - z * sx, y * sx + z * cx
    cy, sy = math.cos(ay), math.sin(ay)
    x, z = x * cy + z * sy, -x * sy + z * cy
    cz, sz = math.cos(az), math.sin(az)
    return x * cz - y * sz, x * sz + y * cz, z


def proyectar(punto, angulos):
    x, y, z = rotar(punto, *angulos)
    escala = 13.5
    centro_x = (ANCHO - 1) / 2
    centro_y = (ALTO - 1) / 2
    return centro_x + x * escala, centro_y - y * escala * 0.5, z


def interpolar_profundidad(punto, triangulo):
    (x, y, z), (x1, y1, z1), (x2, y2, z2) = triangulo
    denominador = (y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)
    if abs(denominador) < 1e-9:
        return None
    a = ((y1 - y2) * (punto[0] - x2) + (x2 - x1) * (punto[1] - y2)) / denominador
    b = ((y2 - y) * (punto[0] - x2) + (x - x2) * (punto[1] - y2)) / denominador
    c = 1 - a - b
    if min(a, b, c) < -1e-6:
        return None
    return a * z + b * z1 + c * z2


def valores_de_caras(resultado):
    return VALORES_CARAS[resultado]


def dentro_del_poligono(x, y, vertices):
    dentro = False
    anterior = vertices[-1]
    for actual in vertices:
        x1, y1 = anterior
        x2, y2 = actual
        if (y1 > y) != (y2 > y):
            cruce = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < cruce:
                dentro = not dentro
        anterior = actual
    return dentro


def dibujar_cubo(angulos, resultado):
    pantalla = [[None for _ in range(ANCHO)] for _ in range(ALTO)]
    valores = valores_de_caras(resultado)
    caras_dibujadas = []

    for nombre, (normal, eje_u, eje_v) in CARAS.items():
        if rotar(normal, *angulos)[2] <= 0:
            continue

        esquinas = [
            tuple(normal[i] - eje_u[i] - eje_v[i] for i in range(3)),
            tuple(normal[i] + eje_u[i] - eje_v[i] for i in range(3)),
            tuple(normal[i] + eje_u[i] + eje_v[i] for i in range(3)),
            tuple(normal[i] - eje_u[i] + eje_v[i] for i in range(3)),
        ]
        puntos = [proyectar(esquina, angulos) for esquina in esquinas]
        poligono = [(p[0], p[1]) for p in puntos]
        caras_dibujadas.append((puntos, normal, eje_u, eje_v, valores[nombre]))

        brillo = max(0, min(2, int((rotar(normal, *angulos)[2] + 1) * 1.4)))
        tono = (246, 250, 255)[brillo]
        fondo_cara = (
            "\033[48;5;229m"
            if valores[nombre] == resultado
            else f"\033[48;5;{tono}m"
        )
        triangulos = [
            (puntos[0], puntos[1], puntos[2]),
            (puntos[0], puntos[2], puntos[3]),
        ]
        min_x = max(0, int(min(p[0] for p in puntos)))
        max_x = min(ANCHO - 1, int(max(p[0] for p in puntos)) + 1)
        min_y = max(0, int(min(p[1] for p in puntos)))
        max_y = min(ALTO - 1, int(max(p[1] for p in puntos)) + 1)

        for fila in range(min_y, max_y + 1):
            for columna in range(min_x, max_x + 1):
                x, y = columna + 0.5, fila + 0.5
                if not dentro_del_poligono(x, y, poligono):
                    continue
                profundidad = next(
                    (
                        z
                        for triangulo in triangulos
                        if (z := interpolar_profundidad((x, y), triangulo)) is not None
                    ),
                    None,
                )
                if profundidad is not None and (
                    pantalla[fila][columna] is None
                    or profundidad > pantalla[fila][columna][0]
                ):
                    pantalla[fila][columna] = (profundidad, " ", "", fondo_cara)

    # Trazar aristas finas evita que el tramado de bloques deforme las caras.
    vertices = [
        (x, y, z)
        for x in (-1, 1)
        for y in (-1, 1)
        for z in (-1, 1)
    ]
    proyectados = [proyectar(v, angulos) for v in vertices]
    for i, punto_a in enumerate(vertices):
        for j in range(i + 1, len(vertices)):
            punto_b = vertices[j]
            if sum(punto_a[k] != punto_b[k] for k in range(3)) != 1:
                continue
            a, b = proyectados[i], proyectados[j]
            pasos = max(abs(round(b[0] - a[0])), abs(round(b[1] - a[1])), 1)
            dx, dy = b[0] - a[0], b[1] - a[1]
            if abs(dy) <= abs(dx) * 0.5:
                caracter_arista = "─"
            elif abs(dx) <= abs(dy) * 0.5:
                caracter_arista = "│"
            else:
                caracter_arista = "╲" if dx * dy > 0 else "╱"

            for paso in range(pasos + 1):
                t = paso / pasos
                x = round(a[0] + (b[0] - a[0]) * t)
                y = round(a[1] + (b[1] - a[1]) * t)
                z = a[2] + (b[2] - a[2]) * t
                if 0 <= x < ANCHO and 0 <= y < ALTO:
                    actual = pantalla[y][x]
                    if actual is None or z >= actual[0] - 0.04:
                        fondo = actual[3] if actual else "\033[48;5;250m"
                        pantalla[y][x] = (
                            z + 0.02,
                            caracter_arista,
                            "\033[38;5;240m",
                            fondo,
                        )

    # Los puntos se proyectan desde cada cara y solo se muestran si esa cara se ve.
    for puntos, normal, eje_u, eje_v, numero in caras_dibujadas:
        for pip_x, pip_y in PUNTOS[numero]:
            ubicacion = tuple(
                normal[i] + eje_u[i] * pip_x + eje_v[i] * pip_y
                for i in range(3)
            )
            px, py, pz = proyectar(ubicacion, angulos)
            x, y = round(px), round(py)
            if 0 <= x < ANCHO and 0 <= y < ALTO:
                actual = pantalla[y][x]
                if actual is None or pz >= actual[0] - 0.1:
                    fondo = actual[3] if actual else "\033[48;5;250m"
                    pantalla[y][x] = (
                        pz + 0.1,
                        "●",
                        "\033[38;5;16m",
                        fondo,
                    )

    return [
        "".join(
            f"{celda[3]}{celda[2]}{celda[1]}{RESET}" if celda else " "
            for celda in fila
        )
        for fila in pantalla
    ]


def mostrar_frame(angulos, resultado):
    lineas = dibujar_cubo(angulos, resultado)
    sys.stdout.write("\033[H" + "\n".join(lineas) + "\n")
    sys.stdout.flush()


def lanzar():
    resultado = secrets.randbelow(6) + 1
    duracion = 1.9
    inicio = time.perf_counter()
    angulo_final = ANGULO_VISTA
    vueltas = (2 * math.pi * 2, 2 * math.pi * 3, 2 * math.pi * 2)
    angulo_inicial = tuple(angulo_final[i] - vueltas[i] for i in range(3))

    while True:
        progreso = min((time.perf_counter() - inicio) / duracion, 1)
        suavizado = 1 - (1 - progreso) ** 3
        angulos = tuple(
            angulo_inicial[i]
            + (angulo_final[i] - angulo_inicial[i]) * suavizado
            for i in range(3)
        )
        mostrar_frame(angulos, resultado)
        if progreso >= 1:
            break
        time.sleep(0.045)

    mostrar_frame(angulo_final, resultado)


def main():
    habilitar_colores()
    sys.stdout.write("\033[2J\033[?25l")
    sys.stdout.flush()
    try:
        mostrar_frame(ANGULO_VISTA, 1)
        while True:
            try:
                orden = input(f"\n{DIM}Enter: lanzar  |  q: salir{RESET} ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                break

            if orden == "q":
                break
            if orden:
                continue

            sys.stdout.write("\033[2J")
            sys.stdout.flush()
            lanzar()
    finally:
        sys.stdout.write(f"\033[?25h{RESET}\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
