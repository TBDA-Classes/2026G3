# =============================================================================
# T30 (F1.3) - Day-ahead forecast of the TOTAL electrical energy of floor 1
#               and reconciliation with the zone x load-type forecasts
# Project : DataPack Energy Forecaster - CeDInt floor 1 (TBDA)
# Input   : cedint_f1_model_ready.csv  (dataset v0.4, long table)
#           [optional] zone_load_forecasts_T29.csv  (forecasts from T29)
# Output  : output/T30/  (xlsx tables, png figures, experiment-log rows)
#
# What the script does
#   1. Builds a hierarchy: TOTAL > zones (NE,NW,SE,SW) and load types > zone x load
#      (bottom series).  The total is the sum of the bottom series, so the
#      hierarchy is "grouped" and fully described by a summing matrix S.
#   2. Trains one day-ahead model per node (LightGBM; ranger as fallback), issued
#      at 00:00 of day D for the 24 h of day D+1 (all lags >= 24 h -> no leakage).
#   3. Produces the floor-total forecast in several ways:
#        - seasonal naive (same hour last week)      [baseline]
#        - direct model on the total                  [base forecast]
#        - bottom-up (sum of zone x load forecasts)
#        - reconciled: OLS, WLS (structural) and MinT-shrink
#   4. Checks coherence (total vs. sum of zones) and evaluates with MAE, RMSE,
#      CV(RMSE) and NMBE against ASHRAE Guideline 14 (CV(RMSE) <= 30 %, |NMBE| <= 10 %).
#   5. Writes the tables, figures and rows for experiment_log.xlsx (T20).
#
# Split (T32): train 2020-06 -> 2022-06 | validation 2022-H2 | test 2023 and 2025
# Required packages: data.table, ggplot2, openxlsx, lightgbm (or ranger),
#                    R.utils (so fread can read .csv.gz)
# =============================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(ggplot2)
  library(openxlsx)
})

# ----------------------------------------------------------------------------
# 1. CONFIGURATION  (adjust column names / paths here only)
# ----------------------------------------------------------------------------
CFG <- list(
  data_file         = "cedint_f1_model_ready.csv",
  t29_forecast_file = "zone_load_forecasts_T29.csv",  # optional, see section 6
  out_dir           = "output/T30",
  author            = "T30 owner",                    # name for the experiment log

  # column names in the clean long table
  col_time   = "timestamp_utc",
  col_zone   = "zone",          # NE / NW / SE / SW  (use "zone_code" for 1NE ... if preferred)
  col_load   = "load_type",     # HVAC / Lighting / Plugs & Sockets / ...
  col_target = "energy_wh_model",
  local_tz   = "Europe/Madrid", # hour / weekday / month features are built in local time

  # Optional use of the include_* columns of the file (NULL = ignore, use dates only).
  # A node is usable only if ALL its bottom series have the flag TRUE in that hour.
  # e.g. train_flag_col = "include_train" or "include_train_no2020";
  #      eval_flag_col  = "include_eval"
  train_flag_col = NULL,
  eval_flag_col  = NULL,

  # Series included in the floor total.  Core loads only by default; the secondary
  # loads and the dead SE Projector are excluded (see section 3 of the backlog).
  include_secondary = FALSE,
  secondary_regex   = "Emergency|Hand|RACK|Projector",

  # optional OUTDOOR weather columns merged in the dataset (Open-Meteo, T26).
  # temp_c / hum_pct / lum_lux / occupancy of the file are INDOOR, zone-level and
  # missing for NE, so they are not used by default (they are not known day-ahead).
  # e.g. c("temp_out_c", "degree_hours")  -> actual weather as proxy of a forecast
  weather_cols = character(0),

  # periods (inclusive dates), as in T32
  train = c("2020-06-01", "2022-06-30"),
  valid = c("2022-07-01", "2022-12-31"),
  test  = list(test_2023 = c("2023-01-01", "2023-12-31"),
               test_2025 = c("2025-01-01", "2025-12-31")),

  lags    = c(24, 48, 168),   # hours; all >= 24 -> valid for a day-ahead forecast
  nrounds = 300,              # fixed LightGBM rounds (tuning belongs to T29)
  seed    = 42
)
stopifnot(168 %in% CFG$lags, all(CFG$lags >= 24))
set.seed(CFG$seed)
dir.create(CFG$out_dir, recursive = TRUE, showWarnings = FALSE)

# ----------------------------------------------------------------------------
# 2. HELPER FUNCTIONS
# ----------------------------------------------------------------------------
metrics <- function(a, p) {
  ok <- is.finite(a) & is.finite(p)
  a <- a[ok]; p <- p[ok]; n <- length(a)
  rmse <- sqrt(mean((a - p)^2))
  cv   <- 100 * rmse / mean(a)
  nmbe <- 100 * sum(p - a) / (n * mean(a))   # + = over-forecast (align with D1 code)
  data.table(n_hours = n, MAE = mean(abs(a - p)), RMSE = rmse,
             CV_RMSE_pct = cv, NMBE_pct = nmbe,
             ASHRAE14_pass = (cv <= 30) & (abs(nmbe) <= 10))
}

# aggregate a matrix of bottom-level values with the summing matrix S
# (NA only if an involved bottom series is NA)
apply_S <- function(Mb, S) {
  out <- do.call(cbind, lapply(seq_len(nrow(S)), function(i)
    rowSums(Mb[, S[i, ] == 1, drop = FALSE])))
  colnames(out) <- rownames(S)
  out
}

build_S <- function(meta) {
  m  <- nrow(meta)
  zs <- sort(unique(meta$zone)); ls <- sort(unique(meta$load))
  S_z <- do.call(rbind, lapply(zs, function(z) as.numeric(meta$zone == z)))
  S_l <- do.call(rbind, lapply(ls, function(l) as.numeric(meta$load == l)))
  S <- rbind(rep(1, m), S_z, S_l, diag(m))
  rownames(S) <- c("TOTAL", paste0("Z_", zs), paste0("L_", ls), meta$series)
  colnames(S) <- meta$series
  S
}

# Schafer-Strimmer shrinkage of the residual covariance (target: its diagonal)
shrink_cov <- function(E) {
  n    <- nrow(E)
  covm <- crossprod(E) / n
  corm <- cov2cor(covm)
  xs   <- scale(E, center = FALSE, scale = sqrt(diag(covm)))
  v    <- (1 / (n * (n - 1))) * (crossprod(xs^2) - (1 / n) * crossprod(xs)^2)
  diag(v) <- 0
  d      <- (corm - diag(ncol(E)))^2
  lambda <- max(min(sum(v) / sum(d), 1), 0)
  list(W = lambda * diag(diag(covm)) + (1 - lambda) * covm, lambda = lambda)
}

# reconcile base forecasts Yh (rows = hours, cols = all nodes) with matrix G
# negative bottom forecasts are set to 0 and the aggregates are rebuilt,
# so that the result stays coherent and physically valid
reconcile <- function(Yh, G, S) {
  Bt <- Yh %*% t(G)
  Bt[Bt < 0] <- 0
  colnames(Bt) <- colnames(S)
  apply_S(Bt, S)
}

has_lgb <- requireNamespace("lightgbm", quietly = TRUE)
if (!has_lgb && !requireNamespace("ranger", quietly = TRUE))
  stop("Install 'lightgbm' (preferred) or 'ranger'.")
message("Learner: ", if (has_lgb) "LightGBM" else "ranger (fallback)")

fit_predict <- function(F, y, tr, pr, fcols) {
  X <- as.matrix(F[, fcols, with = FALSE])
  if (has_lgb) {
    dtr <- lightgbm::lgb.Dataset(data = X[tr, , drop = FALSE], label = y[tr])
    prm <- list(objective = "regression", learning_rate = 0.05, num_leaves = 31,
                min_data_in_leaf = 50, feature_fraction = 0.8,
                bagging_fraction = 0.8, bagging_freq = 1,
                seed = CFG$seed, verbose = -1, num_threads = 2)
    mdl <- lightgbm::lgb.train(params = prm, data = dtr, nrounds = CFG$nrounds)
    p <- predict(mdl, X[pr, , drop = FALSE])
  } else {
    X[is.na(X)] <- -999
    mdl <- ranger::ranger(x = X[tr, , drop = FALSE], y = y[tr],
                          num.trees = 300, seed = CFG$seed)
    p <- predict(mdl, X[pr, , drop = FALSE])$predictions
  }
  pmax(p, 0)
}

# ----------------------------------------------------------------------------
# 3. LOAD AND RESHAPE THE DATA
# ----------------------------------------------------------------------------
raw <- fread(CFG$data_file)
need <- c(CFG$col_time, CFG$col_zone, CFG$col_load, CFG$col_target)
if (length(miss <- setdiff(need, names(raw))))
  stop("Columns not found in the dataset: ", paste(miss, collapse = ", "))
setnames(raw, need, c("ts", "zone", "load", "y"))

if (!inherits(raw$ts, "POSIXct"))
  raw[, ts := as.POSIXct(ts, tz = "UTC",
        tryFormats = c("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                       "%Y-%m-%d %H:%M", "%Y-%m-%d"))]
raw[, ts := as.POSIXct(round(as.numeric(ts) / 3600) * 3600,
                       origin = "1970-01-01", tz = "UTC")]   # align to the hour

if (!CFG$include_secondary)
  raw <- raw[!grepl(CFG$secondary_regex, load, ignore.case = TRUE)]

# bottom series = zone x load type with at least one valid value
meta <- unique(raw[!is.na(y), .(zone, load)])

meta[, series := gsub("[^A-Za-z0-9]+", "_", paste(zone, load, sep = "_"))]
setorder(meta, zone, load)
raw <- merge(raw, meta, by = c("zone", "load"))
cat("\nBottom series included in the floor total:\n"); print(meta)

# wide table on a complete hourly grid (the 902-day gap becomes NA rows)
Wd <- dcast(raw, ts ~ series, value.var = "y", fill = NA_real_,
            fun.aggregate = function(x) if (all(is.na(x))) NA_real_ else sum(x, na.rm = TRUE))
grid <- data.table(ts = seq(min(Wd$ts), max(Wd$ts), by = "hour"))
Wd   <- merge(grid, Wd, by = "ts", all.x = TRUE)
setorder(Wd, ts)
Yb <- as.matrix(Wd[, meta$series, with = FALSE])

# calendar flags from the file (holidays, August low use, COVID 2020) and optional weather
cal_flags <- c("is_holiday", "is_august_low_use", "flag_covid_2020")
present   <- intersect(cal_flags, names(raw))
Fbase <- copy(grid)
if (length(present)) {
  cal <- raw[, lapply(.SD, function(x) as.integer(as.logical(x[1]))),
             by = ts, .SDcols = present]
  Fbase <- merge(Fbase, cal, by = "ts", all.x = TRUE)
}
for (cc in cal_flags) {
  if (!cc %in% names(Fbase)) Fbase[, (cc) := 0L]
  set(Fbase, which(is.na(Fbase[[cc]])), cc, 0L)
}
wc <- intersect(CFG$weather_cols, names(raw))
if (length(wc)) {
  wx <- raw[, lapply(.SD, function(x) mean(x, na.rm = TRUE)), by = ts, .SDcols = wc]
  Fbase <- merge(Fbase, wx, by = "ts", all.x = TRUE)
}
setorder(Fbase, ts)
lt <- as.POSIXlt(Fbase$ts, tz = CFG$local_tz)           # local-time calendar features
Fbase[, `:=`(hour = lt$hour, wday = lt$wday, month = lt$mon + 1L,
             is_weekend = as.integer(lt$wday %in% c(0, 6)))]

# optional include_* flags (matrix: grid hours x bottom series)
flag_matrix <- function(col) {
  if (is.null(col)) return(NULL)
  if (!col %in% names(raw)) stop("Flag column not found: ", col)
  tmp <- raw[, .(ts, series, f = as.numeric(as.logical(get(col))))]
  Fw  <- dcast(tmp, ts ~ series, value.var = "f", fill = NA_real_,
               fun.aggregate = function(x) as.numeric(all(x == 1)))
  Fw  <- merge(grid, Fw, by = "ts", all.x = TRUE)
  setorder(Fw, ts)
  as.matrix(Fw[, meta$series, with = FALSE])
}

# ----------------------------------------------------------------------------
# 4. HIERARCHY AND DAY-AHEAD BASE FORECASTS FOR EVERY NODE
# ----------------------------------------------------------------------------
S       <- build_S(meta)
bottoms <- meta$series
Yall    <- apply_S(Yb, S)            # actuals of every node (NA if a part is missing)
n_node  <- nrow(S); m_bot <- ncol(S)

# usability masks per node (TRUE everywhere if no flag column is configured)
node_flag <- function(col) {
  M <- flag_matrix(col)
  if (is.null(M)) return(matrix(TRUE, nrow(grid), n_node, dimnames = list(NULL, rownames(S))))
  A <- apply_S(M, S)
  U <- A == matrix(rowSums(S), nrow(A), n_node, byrow = TRUE)
  U[is.na(U)] <- FALSE
  U
}
USE_TRAIN <- node_flag(CFG$train_flag_col)
USE_EVAL  <- node_flag(CFG$eval_flag_col)

d <- as.Date(grid$ts)
in_per    <- function(r) d >= as.Date(r[1]) & d <= as.Date(r[2])
idx_train <- in_per(CFG$train)
idx_valid <- in_per(CFG$valid)
idx_test  <- Reduce(`|`, lapply(CFG$test, in_per))
idx_pred  <- idx_valid | idx_test

node_features <- function(y) {
  F <- copy(Fbase)
  for (L in CFG$lags) set(F, j = paste0("lag_", L), value = shift(y, L))
  set(F, j = "mean_prev_24h", value = shift(frollmean(y, 24,  algo = "exact"), 24))
  set(F, j = "mean_prev_7d",  value = shift(frollmean(y, 168, algo = "exact"), 24))
  F
}

Yhat   <- matrix(NA_real_, nrow(grid), n_node, dimnames = list(NULL, rownames(S)))
Lag168 <- Yhat
for (nd in rownames(S)) {
  y  <- Yall[, nd]
  F  <- node_features(y)
  fcols <- setdiff(names(F), "ts")
  Lag168[, nd] <- F$lag_168
  tr <- which(idx_train & !is.na(y) & USE_TRAIN[, nd])
  pr <- which(idx_pred)
  if (length(tr) < 500) {
    warning("Node ", nd, ": fewer than 500 training hours, seasonal naive used.")
    Yhat[pr, nd] <- F$lag_168[pr]
  } else {
    Yhat[pr, nd] <- fit_predict(F, y, tr, pr, fcols)
  }
  message("  base forecast done: ", nd)
}

# ----------------------------------------------------------------------------
# 5. OPTIONAL: USE THE ZONE x LOAD FORECASTS FROM T29 AS BOTTOM FORECASTS
#    File columns: timestamp, zone, load_type, forecast_wh  (valid + test hours)
# ----------------------------------------------------------------------------
if (file.exists(CFG$t29_forecast_file)) {
  f29 <- fread(CFG$t29_forecast_file)
  f29[, ts := as.POSIXct(timestamp, tz = "UTC")]
  f29[, series := gsub("[^A-Za-z0-9]+", "_", paste(zone, load_type, sep = "_"))]
  for (s in intersect(unique(f29$series), bottoms)) {
    z  <- f29[series == s]
    ix <- match(z$ts, grid$ts)
    Yhat[ix[!is.na(ix)], s] <- z$forecast_wh[!is.na(ix)]
  }
  message("Bottom forecasts replaced by T29 forecasts.")
} else {
  message("T29 file not found: the bottom forecasts are produced here (same features/model).")
}

# ----------------------------------------------------------------------------
# 6. RECONCILIATION
#    Common evaluation hours: the total and every bottom series are observed and
#    the 168-h lag exists (so that all methods are compared on the same hours).
# ----------------------------------------------------------------------------
ok <- !is.na(Yall[, "TOTAL"]) & !is.na(Lag168[, "TOTAL"]) &
      complete.cases(Yhat) & USE_EVAL[, "TOTAL"]

valid_rows <- which(idx_valid & ok)
if (length(valid_rows) < 200)
  stop("Fewer than 200 usable validation hours; check the data / periods.")

St <- t(S)
G_ols <- solve(St %*% S) %*% St
Wi_s  <- diag(1 / rowSums(S))                                   # structural weights
G_wls <- solve(St %*% Wi_s %*% S) %*% St %*% Wi_s

E  <- (Yall - Yhat)[valid_rows, , drop = FALSE]                 # out-of-sample residuals
sh <- shrink_cov(E)
W  <- sh$W + diag(1e-6 * mean(diag(sh$W)), n_node)
Wi <- solve(W)
G_mint <- solve(St %*% Wi %*% S) %*% St %*% Wi
message(sprintf("MinT shrinkage intensity lambda = %.3f", sh$lambda))

G_bu <- cbind(matrix(0, m_bot, n_node - m_bot), diag(m_bot))    # bottom-up

rows <- which(idx_pred & ok)
mask <- function(M) { out <- M; out[-rows, ] <- NA_real_; out }
NODE_FC <- list(
  base      = mask(Yhat),
  bottom_up = mask(matrix(NA_real_, nrow(grid), n_node, dimnames = list(NULL, rownames(S)))),
  ols       = mask(matrix(NA_real_, nrow(grid), n_node, dimnames = list(NULL, rownames(S)))),
  wls       = mask(matrix(NA_real_, nrow(grid), n_node, dimnames = list(NULL, rownames(S)))),
  mint      = mask(matrix(NA_real_, nrow(grid), n_node, dimnames = list(NULL, rownames(S))))
)
NODE_FC$bottom_up[rows, ] <- reconcile(Yhat[rows, ], G_bu,   S)
NODE_FC$ols[rows, ]       <- reconcile(Yhat[rows, ], G_ols,  S)
NODE_FC$wls[rows, ]       <- reconcile(Yhat[rows, ], G_wls,  S)
NODE_FC$mint[rows, ]      <- reconcile(Yhat[rows, ], G_mint, S)

naive_total <- rep(NA_real_, nrow(grid)); naive_total[rows] <- Lag168[rows, "TOTAL"]
TOTAL_FC <- c(list(seasonal_naive = naive_total),
              lapply(NODE_FC, function(M) M[, "TOTAL"]))
names(TOTAL_FC)[names(TOTAL_FC) == "base"] <- "direct_total_model"

# ----------------------------------------------------------------------------
# 7. EVALUATION
# ----------------------------------------------------------------------------
PER <- c(list(validation = idx_valid), setNames(lapply(CFG$test, in_per), names(CFG$test)))
PER$test_all <- idx_test

res_total <- rbindlist(lapply(names(PER), function(p) {
  r <- which(PER[[p]] & ok)
  if (!length(r)) return(NULL)
  rbindlist(lapply(names(TOTAL_FC), function(m)
    cbind(period = p, method = m, metrics(Yall[r, "TOTAL"], TOTAL_FC[[m]][r]))))
}))

res_nodes <- rbindlist(lapply(names(PER), function(p) {
  r <- which(PER[[p]] & ok)
  if (!length(r)) return(NULL)
  rbindlist(lapply(c("base", "ols", "wls", "mint"), function(m)
    rbindlist(lapply(rownames(S), function(nd)
      cbind(period = p, method = m, node = nd,
            metrics(Yall[r, nd], NODE_FC[[m]][r, nd]))))))
}))

# coherence: gap between the total and the sum of the bottom series,
# and mean incoherence over ALL aggregate nodes
coh <- rbindlist(lapply(names(PER), function(p) {
  r <- which(PER[[p]] & ok)
  if (!length(r)) return(NULL)
  rbindlist(lapply(names(NODE_FC), function(m) {
    Fm  <- NODE_FC[[m]][r, , drop = FALSE]
    gap <- Fm[, "TOTAL"] - rowSums(Fm[, bottoms, drop = FALSE])
    inc <- abs(apply_S(Fm[, bottoms, drop = FALSE], S) - Fm)
    data.table(period = p, method = m,
               mean_abs_total_gap_wh = mean(abs(gap)),
               total_gap_pct_of_mean_actual = 100 * mean(abs(gap)) / mean(Yall[r, "TOTAL"]),
               mean_incoherence_all_nodes_wh = mean(inc),
               max_abs_gap_wh = max(abs(gap)))
  }))
}))

cat("\n===== FLOOR-1 TOTAL: day-ahead accuracy =====\n")
print(res_total[period %in% c("validation", "test_all"),
                .(period, method, n_hours, MAE = round(MAE), RMSE = round(RMSE),
                  CV_RMSE_pct = round(CV_RMSE_pct, 2), NMBE_pct = round(NMBE_pct, 2),
                  ASHRAE14_pass)])
cat("\n===== COHERENCE (test_all) =====\n")
print(coh[period == "test_all"])

# ----------------------------------------------------------------------------
# 8. FIGURES
# ----------------------------------------------------------------------------
cols <- c(actual = "black", seasonal_naive = "grey60", direct_total_model = "#E69F00",
          bottom_up = "#009E73", mint = "#D55E00")

wk <- rbindlist(lapply(names(CFG$test), function(p) {
  r_all <- which(PER[[p]] & ok)
  if (!length(r_all)) return(NULL)
  days <- sort(unique(d[r_all]))[1:min(7, length(unique(d[r_all])))]
  r <- which(d %in% days & ok)
  data.table(period = p, ts = grid$ts[r], actual = Yall[r, "TOTAL"],
             seasonal_naive = TOTAL_FC$seasonal_naive[r],
             direct_total_model = TOTAL_FC$direct_total_model[r],
             bottom_up = TOTAL_FC$bottom_up[r], mint = TOTAL_FC$mint[r])
}))
if (nrow(wk)) {
  wkl <- melt(wk, id.vars = c("period", "ts"), variable.name = "series", value.name = "wh")
  g1 <- ggplot(wkl, aes(ts, wh / 1000, colour = series)) +
    geom_line(linewidth = 0.5) + facet_wrap(~period, scales = "free_x", ncol = 1) +
    scale_colour_manual(values = cols) +
    labs(title = "Floor-1 total: day-ahead forecast vs actual (first days of each test period)",
         x = NULL, y = "Energy (kWh per hour)", colour = NULL) + theme_minimal()
  ggsave(file.path(CFG$out_dir, "T30_total_forecast_vs_actual.png"), g1, width = 11, height = 7, dpi = 150)
}

r <- which(idx_test & ok)
byh <- rbindlist(lapply(names(TOTAL_FC), function(m)
  data.table(method = m, hour = Fbase$hour[r],
             abs_err = abs(Yall[r, "TOTAL"] - TOTAL_FC[[m]][r]))))[
  , .(MAE_kWh = mean(abs_err) / 1000), by = .(method, hour)]
g2 <- ggplot(byh, aes(hour, MAE_kWh, colour = method)) + geom_line(linewidth = 0.7) +
  labs(title = "Floor-1 total: MAE by hour of day (test periods)", x = "Hour (local time)", y = "MAE (kWh)") +
  theme_minimal()
ggsave(file.path(CFG$out_dir, "T30_total_MAE_by_hour.png"), g2, width = 9, height = 5, dpi = 150)

g3 <- ggplot(coh[period == "test_all"], aes(reorder(method, mean_abs_total_gap_wh), mean_abs_total_gap_wh / 1000)) +
  geom_col(fill = "#56B4E9") + coord_flip() +
  labs(title = "Coherence: |total forecast - sum of zone x load forecasts|",
       x = NULL, y = "Mean absolute gap (kWh per hour)") + theme_minimal()
ggsave(file.path(CFG$out_dir, "T30_coherence_gap.png"), g3, width = 8, height = 4, dpi = 150)

# ----------------------------------------------------------------------------
# 9. EXPORT: tables + rows for the experiment log (T20)
# ----------------------------------------------------------------------------
feat_txt <- paste(c(paste0("lag_", CFG$lags), "mean_prev_24h", "mean_prev_7d",
                    "hour", "wday", "month", "is_weekend", cal_flags, wc), collapse = ", ")
model_txt <- c(seasonal_naive = "Seasonal naive (same hour last week)",
               direct_total_model = paste(if (has_lgb) "LightGBM" else "ranger", "direct on floor total"),
               bottom_up = "Bottom-up (sum of zone x load forecasts)",
               ols = "Reconciliation OLS", wls = "Reconciliation WLS (structural)",
               mint = "Reconciliation MinT-shrink")

log_rows <- res_total[period != "test_all"][, .(
  ID = sprintf("T30-%03d", .I), date = as.character(Sys.Date()), author = CFG$author,
  series = "TOTAL floor 1", features = feat_txt, model = model_txt[method],
  `train period` = paste(CFG$train, collapse = " to "),
  `test period` = vapply(period, function(p) if (p == "validation") paste(CFG$valid, collapse = " to ")
                          else paste(CFG$test[[p]], collapse = " to "), character(1)),
  MAE = round(MAE, 1), RMSE = round(RMSE, 1),
  `CV(RMSE)` = round(CV_RMSE_pct, 2), NMBE = round(NMBE_pct, 2),
  notes = paste0("period=", period, "; ASHRAE14 pass=", ASHRAE14_pass,
                 "; common hours with all series valid; NMBE>0 = over-forecast"))]
fwrite(log_rows, file.path(CFG$out_dir, "T30_experiment_log_rows.csv"))

write.xlsx(list(
  Total_metrics   = res_total,
  Node_metrics    = res_nodes,
  Coherence       = coh,
  Series_used     = meta,
  Summing_matrix  = data.frame(node = rownames(S), S, check.names = FALSE),
  Config          = data.frame(parameter = c("learner", "train", "valid", "test", "lags",
                                             "MinT lambda", "weather", "T29 file used", "series"),
                               value = c(if (has_lgb) "LightGBM" else "ranger",
                                         paste(CFG$train, collapse = " / "),
                                         paste(CFG$valid, collapse = " / "),
                                         paste(unlist(CFG$test), collapse = " / "),
                                         paste(CFG$lags, collapse = ","),
                                         round(sh$lambda, 3),
                                         paste(wc, collapse = ","),
                                         file.exists(CFG$t29_forecast_file),
                                         nrow(meta)))
), file.path(CFG$out_dir, "T30_floor1_total_forecast_results.xlsx"), overwrite = TRUE)

# hourly forecasts (for the dashboard, T36)
fc_out <- data.table(timestamp = grid$ts[rows], actual_wh = Yall[rows, "TOTAL"],
                     seasonal_naive = TOTAL_FC$seasonal_naive[rows],
                     direct_total_model = TOTAL_FC$direct_total_model[rows],
                     bottom_up = TOTAL_FC$bottom_up[rows],
                     reconciled_ols = TOTAL_FC$ols[rows],
                     reconciled_wls = TOTAL_FC$wls[rows],
                     reconciled_mint = TOTAL_FC$mint[rows])
fwrite(fc_out, file.path(CFG$out_dir, "T30_floor1_total_forecast_hourly.csv"))

message("\nT30 finished. Results in: ", normalizePath(CFG$out_dir))
sessionInfo()

