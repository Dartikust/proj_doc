#include "scheduler.h"
#include <math.h>
#include <string.h>

/* ----------------------------------------------------------------
   Генераторы тестовых экземпляров
   ---------------------------------------------------------------- */

// Тест 1: маленький ручной пример (6 заданий, 3 машины)
Instance* test_manual1(void) {
    Instance *inst = inst_create(6, 3);

    double sizes[] = {8, 7, 6, 5, 4, 3};
    memcpy(inst->t, sizes, 6 * sizeof(double));

    // allowed[j][i]
    int allow[6][3] = {
        {1, 1, 0},   // задание 0: M0, M1
        {1, 0, 1},   // задание 1: M0, M2
        {1, 1, 1},   // задание 2: все
        {0, 1, 1},   // задание 3: M1, M2
        {1, 1, 0},   // задание 4: M0, M1
        {1, 1, 1}    // задание 5: все
    };
    for (int j = 0; j < 6; j++)
        for (int i = 0; i < 3; i++)
            inst->allowed[j][i] = allow[j][i];

    return inst;
}

// Тест 2: конфликтный (2 машины, все тяжёлые задания только на M0)
Instance* test_conflict(void) {
    Instance *inst = inst_create(4, 2);

    inst->t[0] = 10; inst->t[1] = 10;
    inst->t[2] =  1; inst->t[3] =  1;

    inst->allowed[0][0] = 1; inst->allowed[0][1] = 0;  // только M0
    inst->allowed[1][0] = 1; inst->allowed[1][1] = 0;  // только M0
    inst->allowed[2][0] = 1; inst->allowed[2][1] = 1;  // обе
    inst->allowed[3][0] = 1; inst->allowed[3][1] = 1;  // обе

    return inst;
}

// Тест 3: случайный (n заданий, m машин)
Instance* test_random(int n, int m, unsigned seed) {
    Instance *inst = inst_create(n, m);
    srand(seed);

    for (int j = 0; j < n; j++) {
        inst->t[j] = 1.0 + (rand() % 20);   // 1..20

        // Каждое задание доступно хотя бы на одной машине
        int cnt = 1 + (rand() % m);          // 1..m
        for (int k = 0; k < cnt; k++)
            inst->allowed[j][rand() % m] = 1;

        // гарантия
        int any = 0;
        for (int i = 0; i < m; i++)
            if (inst->allowed[j][i]) any = 1;
        if (!any) inst->allowed[j][0] = 1;
    }

    return inst;
}

/* ----------------------------------------------------------------
   Запуск всех алгоритмов на одном экземпляре и печать
   ---------------------------------------------------------------- */

void run_all(const char *title, Instance *inst) {
    printf("\n========================================\n");
    printf("%s\n", title);
    printf("n=%d, m=%d\n", inst->n, inst->m);

    // Вывод исходных данных
    printf("Задания: [");
    for (int j = 0; j < inst->n; j++) {
        printf("%.0f", inst->t[j]);
        if (j < inst->n - 1) printf(" ");
    }
    printf("]\nОграничения:\n");
    for (int j = 0; j < inst->n; j++) {
        printf("  J%d -> {", j);
        int first = 1;
        for (int i = 0; i < inst->m; i++) {
            if (inst->allowed[j][i]) {
                if (!first) printf(", ");
                printf("M%d", i);
                first = 0;
            }
        }
        printf("}\n");
    }

    // Запуск
    Solution *s;

    s = algo_greedy_simple(inst);   sol_print("GREEDY SIMPLE",   s, inst); sol_free(s);
    s = algo_greedy_lpt(inst);      sol_print("GREEDY LPT",      s, inst); sol_free(s);
    s = algo_multifit(inst, 40);    sol_print("MULTIFIT",        s, inst); sol_free(s);
    s = algo_local_search(inst);    sol_print("LOCAL SEARCH",    s, inst); sol_free(s);
    s = algo_approx2(inst);         sol_print("2-APPROXIMATION", s, inst); sol_free(s);
}

/* ----------------------------------------------------------------
   Сравнение на многих случайных тестах
   ---------------------------------------------------------------- */

void benchmark(int tests, int n, int m) {
    printf("\n========================================\n");
    printf("СТАТИСТИКА: %d тестов, n=%d, m=%d\n", tests, n, m);
    printf("%-20s %10s %10s\n", "Алгоритм", "Ср.Cmax", "Лучший(%)");
    printf("----------------------------------------------\n");

    double sum[5] = {0};
    int    win[5] = {0};
    const char *names[] = {"Greedy Simple", "Greedy LPT", "Multifit",
                           "Local Search",  "2-Approx"};

    for (int t = 0; t < tests; t++) {
        Instance *inst = test_random(n, m, (unsigned)(t + 100));

        Solution *sol[5];
        sol[0] = algo_greedy_simple(inst);
        sol[1] = algo_greedy_lpt(inst);
        sol[2] = algo_multifit(inst, 40);
        sol[3] = algo_local_search(inst);
        sol[4] = algo_approx2(inst);

        double best = 1e100;
        for (int a = 0; a < 5; a++) {
            sum[a] += sol[a]->makespan;
            if (sol[a]->makespan < best)
                best = sol[a]->makespan;
        }

        for (int a = 0; a < 5; a++)
            if (fabs(sol[a]->makespan - best) < 1e-9)
                win[a]++;

        for (int a = 0; a < 5; a++) sol_free(sol[a]);
        inst_free(inst);
    }

    for (int a = 0; a < 5; a++)
        printf("%-20s %10.2f %9.0f%%\n",
               names[a], sum[a]/tests, 100.0*win[a]/tests);
}

/* ----------------------------------------------------------------
   MAIN
   ---------------------------------------------------------------- */

int main(void) {
    printf("═══════════════════════════════════════\n");
    printf("  ОБОБЩЁННАЯ ЗАДАЧА НАЗНАЧЕНИЯ НАГРУЗКИ\n");
    printf("  Сравнение приближённых алгоритмов\n");
    printf("═══════════════════════════════════════\n");

    // --- Тест 1 ---
    Instance *t1 = test_manual1();
    run_all("ТЕСТ 1: Маленький ручной пример", t1);
    inst_free(t1);

    // --- Тест 2 ---
    Instance *t2 = test_conflict();
    run_all("ТЕСТ 2: Конфликтный пример", t2);
    inst_free(t2);

    // --- Тест 3 ---
    Instance *t3 = test_random(10, 3, 12345);
    run_all("ТЕСТ 3: Случайный пример (10 заданий, 3 машины)", t3);
    inst_free(t3);

    // --- Сравнение ---
    benchmark(30, 15, 4);

    printf("\nГотово.\n");
    return 0;
}