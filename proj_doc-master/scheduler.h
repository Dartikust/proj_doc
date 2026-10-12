#ifndef SCHEDULER_H
#define SCHEDULER_H
#include <stdio.h>
#include <stdlib.h>

/* ============ ОСНОВНЫЕ СТРУКТУРЫ ============ */

// Экземпляр задачи
typedef struct {
    int n;              // количество заданий
    int m;              // количество машин
    double *t;          // размеры заданий (массив длины n)
    int **allowed;      // матрица n x m: allowed[j][i] == 1 => можно
} Instance;

// Решение (назначение)
typedef struct {
    int *assign;        // assign[j] = номер машины для задания j
    double makespan;    // Cmax
} Solution;

/* ============ БАЗОВЫЕ ОПЕРАЦИИ ============ */

// Создать / удалить экземпляр
Instance*  inst_create(int n, int m);
void       inst_free(Instance *inst);

// Создать / удалить решение
Solution*  sol_create(int n);
void       sol_free(Solution *sol);

// Вычислить makespan по назначению
double     sol_eval(const Instance *inst, const Solution *sol);

// Проверить, что все задания назначены на допустимые машины
int        sol_feasible(const Instance *inst, const Solution *sol);

// Загрузка из текстового файла (формат описан в main.c)
Instance*  inst_load(const char *filename);

/* ============ АЛГОРИТМЫ ============ */

Solution*  algo_greedy_simple(const Instance *inst);
Solution*  algo_greedy_lpt   (const Instance *inst);
Solution*  algo_multifit     (const Instance *inst, int iterations);
Solution*  algo_local_search (const Instance *inst);
Solution*  algo_approx2      (const Instance *inst);

/* ============ ВЫВОД ============ */

void       sol_print(const char *algo_name, const Solution *sol, const Instance *inst);

#endif