#!/bin/bash
# >>> conda initialize >>>
if [[ -d "$HOME/miniconda3" ]]; then
    conda_dir="$HOME/miniconda3"
elif [[ -d "$HOME/miniforge3" ]]; then
    conda_dir="$HOME/miniforge3"
else
    exit 1
fi
__conda_setup="$("$conda_dir/bin/conda" 'shell.bash' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "$conda_dir/etc/profile.d/conda.sh" ]; then
        . "$conda_dir/etc/profile.d/conda.sh"
    else
        export PATH="$conda_dir/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<
work_dir=$(dirname -- "$0")
out_dir="$work_dir/../output"
conf_dir="$work_dir/../config"
# conda run -n hups python "$work_dir/check_poweroff.py" >> "$out_dir/check_poweroff.log" 2>&1
# Start and background the HAT first.
conda run -n hups python "$work_dir/run_hat_manager.py" --config "$conf_dir/local.yml" >> "$out_dir/run_hat_manager.log" 2>&1 &
sleep 1
# Check if the Pi is online.
conda run -n hups python "$work_dir/update_online_led.py" "$conf_dir/local.yml" >> "$out_dir/update_online_led.log" 2>&1
# Start and background the tracker daemon.
conda run -n hups python "$work_dir/run_tracker_daemon.py" --config "$conf_dir/local.yml" --profile profile.json >> "$out_dir/run_tracker_daemon.log" 2>&1 &
sleep 5
# Check if the daemon is running.
conda run -n hups python "$work_dir/update_daemon_led.py" "$conf_dir/local.yml" >> "$out_dir/update_daemon_led.log" 2>&1
sleep 25
# Check if the Pi is online.
conda run -n hups python "$work_dir/update_online_led.py" "$conf_dir/local.yml" >> "$out_dir/update_online_led.log" 2>&1
