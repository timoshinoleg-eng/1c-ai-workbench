@{
    Severity = @(
        'Error'
        'Warning'
    )
    IncludeRules = @(
        'PSAvoidUsingCmdletAliases'
        'PSAvoidUsingPositionalParameters'
        'PSAvoidUsingPlainTextForPassword'
        'PSAvoidUsingWMICmdlet'
        'PSUseShouldProcessForStateChangingFunctions'
        'PSUseSupportsShouldProcess'
    )
    ExcludeRules = @(
        'PSUseDeclaredVarsMoreThanAssignments'
        'PSAvoidLongLines'
        'PSUseCompatibleSyntax'
        'PSReservedCmdletChar'
        'PSReservedParams'
        'PSUseShouldProcessForStateChangingFunctions'
        'PSUseSupportsShouldProcess'
        'PSUsePSDriveTypeCmdlet'
    )
    Rules = @{
        PSAvoidLongLines = @{
            Enable     = $true
            MaximumLineLength = 200
        }
    }
}
