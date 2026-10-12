#include "scheduler.h"
#include <string.h>
#include <float.h>
#include <math.h>

/* ================================================================
   БАЗОВЫЕ ФУНКЦИИ
   ================================================================ */

Instance* inst_create(int n, int m) {
    Instance *inst = malloc(sizeof(Instance));
    inst->n = n;
    inst->m = m;

    inst->t = calloc(n, sizeof(double));
    inst->allowed = malloc(n * sizeof(int*));
    for (int j = 0; j < n; j++)
        inst->allowed[j] = calloc(m, sizeof(int));

    return inst;
}

void inst_free(Instance *inst) {
    if (!inst) return;
    for (int j = 0; j < inst->n; j++)
        free(inst->allowed[j]);
    free(inst->allowed);
    free(inst->t);
    free(inst);
}

Solution* sol_create(int n) {
    Solution *sol = malloc(sizeof(Solution));
    sol->assign = malloc(n * sizeof(int));
    for (int j = 0; j < n; j++)
        sol->assign[j] = -1;
    sol->makespan = 0.0;
    return sol;
}

void sol_free(Solution *sol) {
    if (!sol) return;
    free(sol->assign);
    free(sol);
}

double sol_eval(const Instance *inst, const Solution *sol) {
    double *load = calloc(inst->m, sizeof(double));
    for (int j = 0; j < inst->n; j++)
        load[sol->assign[j]] += inst->t[j];

    double max = 0.0;
    for (int i = 0; i < inst->m; i++)
        if (load[i] > max) max = load[i];

    free(load);
    return max;
}

int sol_feasible(const Instance *inst, const Solution *sol) {
    for (int j = 0; j < inst->n; j++) {
        int m = sol->assign[j];
        if (m < 0 || m >= inst->m) return 0;
        if (!inst->allowed[j][m])  return 0;
    }
    return 1;
}

Instance* inst_load(const char *filename) {
    FILE *f = fopen(filename, "r");
    if (!f) {
        fprintf(stderr, "Ошибка: не могу открыть '%s'\n", filename);
        return NULL;
    }

    int n, m;
    fscanf(f, "%d %d", &n, &m);

    Instance *inst = inst_create(n, m);

    for (int j = 0; j < n; j++)
        fscanf(f, "%lf", &inst->t[j]);

    for (int j = 0; j < n; j++)
        for (int i = 0; i < m; i++)
            fscanf(f, "%d", &inst->allowed[j][i]);

    fclose(f);
    return inst;
}

/* ================================================================
   ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (внутренние)
   ================================================================ */

// Найти допустимую машину с минимальной нагрузкой
static int pick_min_load(const double *load, const int *allow, int m) {
    int best = -1;
    double min = DBL_MAX;
    for (int i = 0; i < m; i++) {
        if (allow[i] && load[i] < min) {
            min = load[i];
            best = i;
        }
    }
    return best;
}

// Вспомогательная структура для сортировки заданий по убыванию размера
typedef struct {
    int    idx;
    double size;
} JobRec;

static int cmp_desc(const void *a, const void *b) {
    double d = ((JobRec*)b)->size - ((JobRec*)a)->size;
    return (d > 0) ? 1 : (d < 0) ? -1 : 0;
}

// Отсортировать индексы заданий по убыванию t[j]
static JobRec* jobs_sorted(const Instance *inst) {
    JobRec *arr = malloc(inst->n * sizeof(JobRec));
    for (int j = 0; j < inst->n; j++) {
        arr[j].idx  = j;
        arr[j].size = inst->t[j];
    }
    qsort(arr, inst->n, sizeof(JobRec), cmp_desc);
    return arr;
}

/* ================================================================
   АЛГОРИТМ 1: Greedy Simple (без сортировки)
   ================================================================ */

Solution* algo_greedy_simple(const Instance *inst) {
    Solution *sol = sol_create(inst->n);
    double *load = calloc(inst->m, sizeof(double));

    for (int j = 0; j < inst->n; j++) {
        int m = pick_min_load(load, inst->allowed[j], inst->m);
        if (m == -1) {           // не должно происходить
            free(load);
            sol_free(sol);
            return NULL;
        }
        sol->assign[j] = m;
        load[m] += inst->t[j];
    }

    sol->makespan = sol_eval(inst, sol);
    free(load);
    return sol;
}

/* ================================================================
   АЛГОРИТМ 2: Greedy LPT (с сортировкой)
   ================================================================ */

Solution* algo_greedy_lpt(const Instance *inst) {
    Solution *sol = sol_create(inst->n);
    double *load = calloc(inst->m, sizeof(double));
    JobRec *order = jobs_sorted(inst);

    for (int k = 0; k < inst->n; k++) {
        int j = order[k].idx;
        int m = pick_min_load(load, inst->allowed[j], inst->m);
        if (m == -1) {
            free(load); free(order);
            sol_free(sol);
            return NULL;
        }
        sol->assign[j] = m;
        load[m] += inst->t[j];
    }

    sol->makespan = sol_eval(inst, sol);
    free(load);
    free(order);
    return sol;
}

/* ================================================================
   АЛГОРИТМ 3: Multifit (бинарный поиск по Cmax)
   ================================================================ */

// Проверка: можно ли уложиться в лимит limit
static int can_fit(const Instance *inst, double limit, int *assign) {
    double *load = calloc(inst->m, sizeof(double));
    JobRec *order = jobs_sorted(inst);
    int ok = 1;

    for (int k = 0; k < inst->n; k++) {
        int j = order[k].idx;
        int placed = 0;

        // Пытаемся найти машину, не выходя за limit
        for (int i = 0; i < inst->m; i++) {
            if (inst->allowed[j][i] &&
                load[i] + inst->t[j] <= limit + 1e-9) {
                assign[j] = i;
                load[i] += inst->t[j];
                placed = 1;
                break;
            }
        }

        // Не влезло — кладём на минимально загруженную допустимую
        if (!placed) {
            int m = pick_min_load(load, inst->allowed[j], inst->m);
            if (m == -1) { ok = 0; break; }
            assign[j] = m;
            load[m] += inst->t[j];
        }
    }

    free(load);
    free(order);
    return ok;
}

Solution* algo_multifit(const Instance *inst, int iters) {
    Solution *sol = sol_create(inst->n);

    // Границы бинарного поиска
    double lo = 0.0, hi = 0.0;
    for (int j = 0; j < inst->n; j++) {
        if (inst->t[j] > lo) lo = inst->t[j];
        hi += inst->t[j];
    }
    if (hi < lo * inst->m) hi = lo * inst->m;

    int    *best_assign = malloc(inst->n * sizeof(int));
    double  best_val    = hi;

    for (int iter = 0; iter < iters; iter++) {
        double mid = (lo + hi) / 2.0;
        int *tmp = malloc(inst->n * sizeof(int));
        for (int j = 0; j < inst->n; j++) tmp[j] = -1;

        if (can_fit(inst, mid, tmp)) {
            // Считаем реальный makespan (может быть меньше mid)
            double *ld = calloc(inst->m, sizeof(double));
            double actual = 0.0;
            for (int j = 0; j < inst->n; j++) {
                ld[tmp[j]] += inst->t[j];
                if (ld[tmp[j]] > actual) actual = ld[tmp[j]];
            }
            free(ld);

            if (actual < best_val) {
                best_val = actual;
                memcpy(best_assign, tmp, inst->n * sizeof(int));
            }
            hi = mid;
        } else {
            lo = mid;
        }

        free(tmp);
        if (hi - lo < 1e-6) break;
    }

    memcpy(sol->assign, best_assign, inst->n * sizeof(int));
    sol->makespan = sol_eval(inst, sol);
    free(best_assign);
    return sol;
}

/* ================================================================
   АЛГОРИТМ 4: Локальный поиск (1-exchange)
   ================================================================ */

Solution* algo_local_search(const Instance *inst) {
    // Начальное решение – LPT
    Solution *sol = algo_greedy_lpt(inst);
    if (!sol) return NULL;

    double *load = calloc(inst->m, sizeof(double));
    int improved = 1;
    int max_iter = 500;

    for (int iter = 0; iter < max_iter && improved; iter++) {
        improved = 0;

        // Текущие нагрузки
        for (int i = 0; i < inst->m; i++) load[i] = 0.0;
        for (int j = 0; j < inst->n; j++)
            load[sol->assign[j]] += inst->t[j];

        double cur = sol->makespan;

        // Перебираем все задания
        for (int j = 0; j < inst->n && !improved; j++) {
            int old_m = sol->assign[j];

            // Пробуем все допустимые машины, кроме текущей
            for (int new_m = 0; new_m < inst->m; new_m++) {
                if (new_m == old_m || !inst->allowed[j][new_m])
                    continue;

                double new_old = load[old_m] - inst->t[j];
                double new_new = load[new_m] + inst->t[j];
                double candidate = new_old;
                if (new_new > candidate) candidate = new_new;

                // Проверяем остальные машины
                for (int i = 0; i < inst->m; i++) {
                    if (i == old_m || i == new_m) continue;
                    if (load[i] > candidate) candidate = load[i];
                }

                // Улучшилось?
                if (candidate < cur - 1e-9) {
                    load[old_m] -= inst->t[j];
                    load[new_m] += inst->t[j];
                    sol->assign[j] = new_m;
                    sol->makespan = candidate;
                    improved = 1;
                    break;
                }
            }
        }
    }

    sol->makespan = sol_eval(inst, sol);
    free(load);
    return sol;
}

/* ================================================================
   АЛГОРИТМ 5: 2-приближение (идея LP-релаксации)
   ================================================================ */

Solution* algo_approx2(const Instance *inst) {
    double total = 0.0, max_job = 0.0;
    for (int j = 0; j < inst->n; j++) {
        total += inst->t[j];
        if (inst->t[j] > max_job) max_job = inst->t[j];
    }

    double lb = max_job;
    double avg = total / inst->m;
    if (avg > lb) lb = avg;

    double bound = 2.0 * lb;

    Solution *sol  = sol_create(inst->n);
    double   *load = calloc(inst->m, sizeof(double));
    JobRec   *order = jobs_sorted(inst);

    for (int k = 0; k < inst->n; k++) {
        int j = order[k].idx;
        int placed = 0;

        for (int i = 0; i < inst->m; i++) {
            if (inst->allowed[j][i] &&
                load[i] + inst->t[j] <= bound + 1e-9) {
                sol->assign[j] = i;
                load[i] += inst->t[j];
                placed = 1;
                break;
            }
        }

        if (!placed) {
            int m = pick_min_load(load, inst->allowed[j], inst->m);
            if (m == -1) {
                free(load); free(order);
                sol_free(sol);
                return NULL;
            }
            sol->assign[j] = m;
            load[m] += inst->t[j];
        }
    }

    sol->makespan = sol_eval(inst, sol);
    free(load);
    free(order);
    return sol;
}

/* ================================================================
   ВЫВОД
   ================================================================ */

void sol_print(const char *algo_name, const Solution *sol, const Instance *inst) {
    printf("\n=== %s ===\n", algo_name);
    if (!sol) {
        printf("  FAIL\n");
        return;
    }

    printf("  Makespan = %.2f\n", sol->makespan);

    double *load = calloc(inst->m, sizeof(double));
    for (int j = 0; j < inst->n; j++)
        load[sol->assign[j]] += inst->t[j];

    for (int i = 0; i < inst->m; i++) {
        printf("  M%d: %.1f  [", i, load[i]);
        int first = 1;
        for (int j = 0; j < inst->n; j++) {
            if (sol->assign[j] == i) {
                if (!first) printf(", ");
                printf("J%d(%.0f)", j, inst->t[j]);
                first = 0;
            }
        }
        printf("]\n");
    }

    free(load);
}